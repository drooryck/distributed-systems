import socket
import threading
import sqlite3
from queue import Queue
import json
import struct
import argparse
import struct

from protocol import Message, JSONProtocolHandler, CustomProtocolHandler


#############################
# 1. SERVER CLASS
#############################

class Server:
    """
    Example chat server with a coarse-grained lock (one request at a time).
    
    Key actions:
      1) signup
      2) login
      3) logout
      4) count_unread
      5) send_message
      6) send_messages_to_client (NEW)
      7) fetch_away_msgs (NEW)
      8) list_accounts
      9) delete_messages
      10) delete_account
      11) reset_db
    """
    def __init__(self, host="10.250.120.214", port=5555, protocol="json", db_name="chat.db"):
        self.host = host
        self.port = port
        self.protocol = protocol.lower()
        if self.protocol == "json":
            self.protocol_handler = JSONProtocolHandler()
        else:
            self.protocol_handler = CustomProtocolHandler()

        self.db_name = db_name

        self.client_queues = {}     # {client_id: Queue()}
        self.logged_in_users = {}   # {client_id: username}
        self.server_lock = threading.Lock()

        self._init_db()

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                recipient TEXT,
                content TEXT,
                to_deliver INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    def start_server(self):
        if self.protocol == "json":
            self.protocol_handler = JSONProtocolHandler()
        else:
            self.protocol_handler = CustomProtocolHandler()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        print(f"Server listening on {self.host}:{self.port} (protocol={self.protocol})")

        try:
            while True:
                conn, addr = self.sock.accept()
                client_id = addr
                self.client_queues[client_id] = Queue()
                thread = threading.Thread(target=self.handle_client, args=(conn, client_id))
                thread.start()
        except KeyboardInterrupt:
            print("Shutting down server...")
        finally:
            self.sock.close()

    def handle_client(self, conn, client_id):
        print(f"[+] Client connected: {client_id}")
        try:
            while True:
                message = self.protocol_handler.receive(conn)
                if not message:
                    print(f"[-] Client disconnected: {client_id}")
                    break
                self.client_queues[client_id].put(message)
                self.process_job_queue(client_id, conn)
        except Exception as e:
            print(f"Error handling {client_id}: {e}")
        finally:
            conn.close()
            if client_id in self.client_queues:
                del self.client_queues[client_id]
            if client_id in self.logged_in_users:
                del self.logged_in_users[client_id]

    def process_job_queue(self, client_id, conn):
        queue = self.client_queues[client_id]
        while not queue.empty():
            job = queue.get()
            self.process_client_action(client_id, job, conn)

    def process_client_action(self, client_id, message: Message, conn):
        with self.server_lock:
            msg_type = message.msg_type
            data = message.data

            if msg_type == "signup":
                self._action_signup(client_id, data, conn)
            elif msg_type == "login":
                self._action_login(client_id, data, conn)
            elif msg_type == "logout":
                self._action_logout(client_id, data, conn)
            elif msg_type == "count_unread":
                self._action_count_unread(client_id, data, conn)
            elif msg_type == "send_message":
                self._action_send_message(client_id, data, conn)
            elif msg_type == "send_messages_to_client":
                self._action_send_messages_to_client(client_id, data, conn)
            elif msg_type == "fetch_away_msgs":
                self._action_fetch_away_messages(client_id, data, conn)
            elif msg_type == "list_accounts":
                self._action_list_accounts(client_id, data, conn)
            elif msg_type == "delete_messages":
                self._action_delete_messages(client_id, data, conn)
            elif msg_type == "delete_account":
                self._action_delete_account(client_id, data, conn)
            elif msg_type == "reset_db":
                self._action_reset_db(client_id, data, conn)
            else:
                resp = {"status": "error", "msg": f"Unknown action: {msg_type}"}
                self.protocol_handler.send(conn, Message("response", resp))

    #############################
    # ACTION METHODS (ORDERED)
    #############################

    # 1) signup
    def _action_signup(self, client_id, data, conn):
        username = data.get("username")
        password_hash = data.get("password")
        if not username or not password_hash:
            resp = {"status": "error", "msg": "Invalid signup data."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        c = self.conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        row = c.fetchone()
        if row:
            resp = {"status": "error", "msg": "Username already taken."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        self.conn.commit()
        resp = {"status": "ok", "msg": "Signup successful. Please login."}
        self.protocol_handler.send(conn, Message("response", resp))

    # 2) login
    def _action_login(self, client_id, data, conn):
        username = data.get("username")
        password_hash = data.get("password")
        if not username or not password_hash:
            resp = {"status": "error", "msg": "Invalid login data."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        # Already logged in by any client?
        if username in self.logged_in_users.values():
            resp = {"status": "error", "msg": "This user is already logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        # This client is already logged in as another user?
        if client_id in self.logged_in_users:
            current_user = self.logged_in_users[client_id]
            if current_user != username:
                resp = {"status": "error", "msg": "Client is already logged in with another user."}
                self.protocol_handler.send(conn, Message("response", resp))
                return

        c = self.conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        row = c.fetchone()
        if not row:
            resp = {"status": "error", "msg": "Username not found."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        stored_hash = row[0]
        if stored_hash != password_hash:
            resp = {"status": "error", "msg": "Wrong password."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        # Login success
        self.logged_in_users[client_id] = username
        # im not going to use the count action here because i dont want too many dependencies of actions on other actions.
        c.execute("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE recipient=? AND to_deliver=0
        """, (username,))
        (unread_count,) = c.fetchone()
        resp = {
            "status": "ok",
            "msg": "Login successful.",
            "unread_count": unread_count
        }
        self.protocol_handler.send(conn, Message("response", resp))

    # 3) logout
    def _action_logout(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return
        del self.logged_in_users[client_id]
        resp = {"status": "ok", "msg": "You have been logged out."}
        self.protocol_handler.send(conn, Message("response", resp))

    # 4) count_unread
    def _action_count_unread(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        c = self.conn.cursor()
        c.execute("""
            SELECT COUNT(*) 
            FROM messages
            WHERE recipient=? AND to_deliver=0
        """, (current_user,))
        (unread_count,) = c.fetchone()
        resp = {
            "status": "ok",
            "msg": "Count of away messages.",
            "unread_count": unread_count
        }
        self.protocol_handler.send(conn, Message("response", resp))

    # 5) send_message
    def _action_send_message(self, client_id, data, conn):
        sender = data.get("sender")
        recipient = data.get("recipient")
        content = data.get("content")

        current_user = self.logged_in_users.get(client_id)
        if current_user != sender:
            resp = {"status": "error", "msg": "You are not logged in as this sender."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        if not recipient or not content:
            resp = {"status": "error", "msg": "Recipient and content required."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        c = self.conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (recipient,))
        row = c.fetchone()
        if not row:
            resp = {"status": "error", "msg": "Recipient does not exist."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        # If the recipient is logged in, we mark to_deliver=1 immediately
        recipient_is_logged_in = any(u == recipient for u in self.logged_in_users.values())
        delivered_value = 1 if recipient_is_logged_in else 0

        # Insert into messages with to_deliver=(0 or 1)
        c.execute("""
            INSERT INTO messages (sender, recipient, content, to_deliver)
            VALUES (?, ?, ?, ?)
        """, (sender, recipient, content, delivered_value))
        self.conn.commit()

        resp = {"status": "ok", "msg": "Message stored."}
        self.protocol_handler.send(conn, Message("response", resp))


    # 6) send_messages_to_client
    #    - returns any messages that are to be delivered (to_deliver==1), marking them delivered=1.
    def _action_send_messages_to_client(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        c = self.conn.cursor()
        c.execute("""
            SELECT id, sender, content, to_deliver
            FROM messages
            WHERE recipient=? AND to_deliver=1
            ORDER BY id ASC
        """, (current_user,))
        rows = c.fetchall()

        results = []
        for (msg_id, snd, content, to_deliver) in rows:
            results.append({
                "id": msg_id,
                "sender": snd,
                "content": content,
                "to_deliver": to_deliver
            })

        resp = {"status": "ok", "msg": results}
        self.protocol_handler.send(conn, Message("response", resp))

    # 7) fetch_away_messages
    #    - returns a specified number of messages that have to_deliver==0
    #    - doesn't even need to send anything back to be honest.
    def _action_fetch_away_messages(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        # We'll allow the user to specify a limit, default=10
        limit = data.get("limit", 10)

        c = self.conn.cursor()
        # Find messages that have not been delivered yet
        c.execute("""
            SELECT id, sender, content
            FROM messages
            WHERE recipient=? AND to_deliver=0
            ORDER BY id ASC
            LIMIT ?
        """, (current_user, limit))
        rows = c.fetchall()

        # Mark them delivered
        message_ids = [str(r[0]) for r in rows]
        if message_ids:
            placeholders = ",".join(["?"] * len(message_ids))
            query = f"UPDATE messages SET to_deliver=1 WHERE id IN ({placeholders})"
            c.execute(query, message_ids)
            self.conn.commit()

        # Build the list to send back
        fetched_messages = []
        for row in rows:
            msg_id, snd, content = row
            fetched_messages.append({
                "id": msg_id,
                "sender": snd,
                "content": content
            })

        resp = {"status": "ok", "msg": fetched_messages}
        self.protocol_handler.send(conn, Message("response", resp))


    # 8) list_accounts
    def _action_list_accounts(self, client_id, data, conn):
        pattern = data.get("pattern")
        start = data.get("start", 0)
        count = data.get("count", 10)

        if not pattern:
            resp = {"status": "error", "msg": "No pattern provided."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        sql_pattern = f"%{pattern}%"
        c = self.conn.cursor()
        c.execute("""
            SELECT username 
            FROM users 
            WHERE username LIKE ?
            ORDER BY username 
            LIMIT ? OFFSET ?
        """, (sql_pattern, count, start))
        rows = c.fetchall()

        matched = [r[0] for r in rows]
        resp = {"status": "ok", "users": matched}
        self.protocol_handler.send(conn, Message("response", resp))

    # 9) delete_messages
    def _action_delete_messages(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return
        message_ids = data.get("message_ids_to_delete", [])
        if not isinstance(message_ids, list) or not message_ids:
            resp = {"status": "error", "msg": "No valid message IDs provided."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        c = self.conn.cursor()
        placeholders = ",".join(["?"] * len(message_ids))
        query = f"DELETE FROM messages WHERE id IN ({placeholders}) AND recipient=?"
        params = message_ids + [current_user]
        c.execute(query, params)
        deleted_count = c.rowcount
        self.conn.commit()

        resp = {
            "status": "ok",
            "msg": f"Deleted {deleted_count} messages.",
            "deleted_count": deleted_count
        }
        self.protocol_handler.send(conn, Message("response", resp))

    # 10) delete_account
    def _action_delete_account(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        c = self.conn.cursor()
        # Delete all messages from AND to this user
        c.execute("DELETE FROM messages WHERE sender=? OR recipient=?", (current_user, current_user))
        # Delete the user record
        c.execute("DELETE FROM users WHERE username=?", (current_user,))
        self.conn.commit()

        del self.logged_in_users[client_id]
        resp = {
            "status": "ok",
            "msg": f"Account '{current_user}' has been deleted. All associated messages are removed."
        }
        self.protocol_handler.send(conn, Message("response", resp))

    # 11) reset_db
    def _action_reset_db(self, client_id, data, conn):
        print("Resetting database upon client request...")
        c = self.conn.cursor()
        c.execute("DROP TABLE IF EXISTS users;")
        c.execute("DROP TABLE IF EXISTS messages;")

        c.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                recipient TEXT,
                content TEXT,
                to_deliver INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()
        print("Database reset complete.")
        resp = {"status": "ok", "msg": "Database reset."}
        self.protocol_handler.send(conn, Message("response", resp))

    #############################
    # UTILITIES
    #############################

    def _store_message(self, sender, recipient, content):
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO messages (sender, recipient, content, to_deliver)
            VALUES (?, ?, ?, ?)
        """, (sender, recipient, content, 0))
        self.conn.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the messaging server.")
    parser.add_argument("--host", type=str, default="10.250.120.214", help="IP address to bind the server (default: 10.250.120.214)")
    parser.add_argument("--port", type=int, default=5555, help="Port to listen on (default: 5555)")
    parser.add_argument("--protocol", type=str, choices=["json", "custom"], default="json", help="Protocol to use (default: json)")

    args = parser.parse_args()

    server = Server(host=args.host, port=args.port, protocol=args.protocol)
    server.start_server()

