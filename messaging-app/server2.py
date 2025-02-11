import socket
import threading
import sqlite3
from queue import Queue
import json
import struct

#############################
# 1. MESSAGE CLASS
#############################
class Message:
    """
    Represents a generic message object that can be used for both
    JSON and custom wire protocols.
    """
    def __init__(self, msg_type, data):
        self.msg_type = msg_type
        self.data = data

    def __repr__(self):
        return f"<Message type={self.msg_type}, data={self.data}>"

#############################
# 2. PROTOCOL HANDLERS
#############################

class JSONProtocolHandler:
    """
    Handles sending and receiving messages in JSON format.
    Assumes length-prefixing using 4 bytes (struct.pack).
    """
    def send(self, conn, message: Message):
        payload = {
            "msg_type": message.msg_type,
            "data": message.data
        }
        encoded = json.dumps(payload).encode("utf-8")
        conn.sendall(struct.pack("!I", len(encoded)))
        conn.sendall(encoded)

    def receive(self, conn):
        length_prefix = conn.recv(4)
        if not length_prefix:
            return None
        (length,) = struct.unpack("!I", length_prefix)
        if length == 0:
            return None
        data = conn.recv(length)
        if not data:
            return None
        payload = json.loads(data.decode("utf-8"))
        msg_type = payload.get("msg_type", "")
        msg_data = payload.get("data", {})
        return Message(msg_type, msg_data)


class CustomProtocolHandler:
    """
    Handles sending and receiving messages with a custom (binary) wire protocol.
    This is just a minimal placeholder.
    """
    def send(self, conn, message: Message):
        msg_type_encoded = message.msg_type.encode("utf-8")
        data_str = json.dumps(message.data)
        data_encoded = data_str.encode("utf-8")

        combined = msg_type_encoded + b"\x00" + data_encoded
        conn.sendall(struct.pack("!I", len(combined)))
        conn.sendall(combined)

    def receive(self, conn):
        length_prefix = conn.recv(4)
        if not length_prefix:
            return None
        (length,) = struct.unpack("!I", length_prefix)
        if length == 0:
            return None
        combined = conn.recv(length)
        if not combined:
            return None
        parts = combined.split(b"\x00", 1)
        if len(parts) < 2:
            return None
        msg_type_encoded, data_encoded = parts
        msg_type = msg_type_encoded.decode("utf-8")
        data_dict = json.loads(data_encoded.decode("utf-8"))
        return Message(msg_type, data_dict)

#############################
# 3. SERVER CLASS
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
    def __init__(self, host="127.0.0.1", port=5555, protocol="json", db_name="chat.db"):
        self.host = host
        self.port = port
        self.protocol = protocol.lower()
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
                delivered INTEGER DEFAULT 0,
                sent_while_away INTEGER DEFAULT 0
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
                self._action_fetch_away_msgs(client_id, data, conn)
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
            WHERE recipient=? AND delivered=0 AND sent_while_away=1
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
            WHERE recipient=? AND delivered=0 AND sent_while_away=1
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

        recipient_is_logged_in = any(u == recipient for u in self.logged_in_users.values())
        sent_while_away = 0 if recipient_is_logged_in else 1
        self._store_message(sender, recipient, content, sent_while_away)

        resp = {"status": "ok", "msg": "message stored"}
        self.protocol_handler.send(conn, Message("response", resp))

    # 6) send_messages_to_client
    #    - returns any (delivered=0 AND sent_while_away=1) messages, marking them delivered=1
    #      PLUS any (delivered=1) messages (regardless of sent_while_away).
    def _action_send_messages_to_client(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        c = self.conn.cursor()
        # We want either (delivered=0, sent_while_away=1) OR (delivered=1, any sent_while_away)
        # That means: (delivered=0 AND sent_while_away=1) OR (delivered=1)
        c.execute("""
            SELECT id, sender, content, delivered, sent_while_away
            FROM messages
            WHERE recipient=? 
              AND (
                (delivered=0 AND sent_while_away=1)
                OR (delivered=1)
              )
            ORDER BY id ASC
        """, (current_user,))
        rows = c.fetchall()

        # Mark away/undelivered messages as delivered
        # Those with delivered=0 and sent_while_away=1
        away_ids = [str(r[0]) for r in rows if r[3] == 0 and r[4] == 1]
        if away_ids:
            placeholders = ",".join(["?"] * len(away_ids))
            query = f"UPDATE messages SET delivered=1 WHERE id IN ({placeholders})"
            c.execute(query, away_ids)
            self.conn.commit()

        results = []
        for (msg_id, snd, content, delivered, away) in rows:
            results.append({
                "id": msg_id,
                "sender": snd,
                "content": content,
                "delivered": delivered,
                "sent_while_away": away
            })

        resp = {"status": "ok", "messages": results}
        self.protocol_handler.send(conn, Message("response", resp))

    # 7) fetch_away_msgs
    #    - returns a specified number of messages where sent_while_away=1
    def _action_fetch_away_msgs(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("response", resp))
            return

        limit = data.get("limit", 5)

        c = self.conn.cursor()
        c.execute("""
            SELECT id, sender, content
            FROM messages
            WHERE recipient=? AND sent_while_away=1
            ORDER BY id ASC
            LIMIT ?
        """, (current_user, limit))
        rows = c.fetchall()

        # Build output
        away_list = []
        for (msg_id, snd, content) in rows:
            away_list.append({"id": msg_id, "sender": snd, "content": content})

        resp = {"status": "ok", "messages": away_list}
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
                delivered INTEGER DEFAULT 0,
                sent_while_away INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()
        print("✅ Database reset complete.")
        resp = {"status": "ok", "msg": "Database reset."}
        self.protocol_handler.send(conn, Message("response", resp))

    #############################
    # UTILITIES
    #############################

    def _store_message(self, sender, recipient, content, sent_while_away):
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO messages (sender, recipient, content, delivered, sent_while_away)
            VALUES (?, ?, ?, ?, ?)
        """, (sender, recipient, content, 0, sent_while_away))
        self.conn.commit()


if __name__ == "__main__":
    server = Server(protocol="json")
    server.start_server()
