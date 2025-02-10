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
        """
        :param msg_type: A string identifying the type of message/action (e.g. 'login', 'signup', 'send_msg').
        :param data: Dictionary or object holding the message data.
        """
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
        # Convert the Message to JSON
        payload = {
            "msg_type": message.msg_type,
            "data": message.data
        }
        encoded = json.dumps(payload).encode("utf-8")

        # Prepend message size as 4 bytes (network byte order)
        conn.sendall(struct.pack("!I", len(encoded)))
        conn.sendall(encoded)

    def receive(self, conn):
        # First read the 4-byte length prefix
        length_prefix = conn.recv(4)
        if not length_prefix:
            return None

        (length,) = struct.unpack("!I", length_prefix)
        if length == 0:
            return None

        # Read the actual JSON payload
        data = conn.recv(length)
        if not data:
            return None

        payload = json.loads(data.decode("utf-8"))
        msg_type = payload.get("msg_type", "")
        msg_data = payload.get("data", {})
        return Message(msg_type, msg_data)


class CustomProtocolHandler:
    """
    Handles sending and receiving messages using a custom (binary) wire protocol.
    This is just a minimal placeholder to illustrate the structure.
    """
    def send(self, conn, message: Message):
        # For demonstration, let’s do:
        # [4-byte big-endian length][msg_type as ASCII][0x00 separator][raw data as ASCII]
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

        # Split at 0x00 to separate msg_type from data
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
    Example chat server using SQLite for storage, job queues, and pluggable protocols.
    Includes:
      - signup (no auto-login)
      - login (assumes client sends SHA-256 hashed password)
      - send_message (checks recipient existence)
      - fetch_messages

    New Requirements:
      - Coarse-grained lock to prevent DB corruption: all actions in process_client_action are locked.
      - If user is already logged in (by another client), disallow login.
      - If client is already logged in as someone, also disallow logging in as a new user.
    """
    def __init__(self, host="127.0.0.1", port=5555, protocol="json", db_name="chat.db"):
        self.host = host
        self.port = port
        self.protocol = protocol.lower()  # 'json' or 'custom'
        self.db_name = db_name

        # Each client will have a queue storing jobs (messages/requests)
        self.client_queues = {}  # {client_id: Queue()}

        # Track which user is currently logged in on a given client_id
        self.logged_in_users = {}  # {client_id: username}

        # A single lock for coarse-grained synchronization
        self.server_lock = threading.Lock()

        # Initialize database
        self._init_db()

    def _init_db(self):
        """
        Initialize SQLite tables if they don't already exist.
        For simplicity, store everything in one file-based DB.
        """
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        cursor = self.conn.cursor()

        # Create a users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)

        # Create a messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                recipient TEXT,
                content TEXT,
                delivered INTEGER DEFAULT 0
            );
        """)

        self.conn.commit()

    def start_server(self):
        """
        Start listening for client connections.
        Depending on the chosen protocol, create the appropriate handler.
        """
        if self.protocol == "json":
            self.protocol_handler = JSONProtocolHandler()
        else:
            self.protocol_handler = CustomProtocolHandler()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # IPv4, TCP
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        print(f"Server listening on {self.host}:{self.port} (protocol={self.protocol})")

        try:
            while True:
                conn, addr = self.sock.accept()
                client_id = addr  # You can use any unique identifier

                # Create a job queue for this client
                self.client_queues[client_id] = Queue()

                # Spawn a thread to handle communication
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(conn, client_id)
                )
                thread.start()
        except KeyboardInterrupt:
            print("Shutting down server...")
        finally:
            self.sock.close()

    def handle_client(self, conn, client_id):
        """
        Continuously receive messages from the client and add them to its job queue.
        Then process the queue.
        """
        print(f"[+] Client connected: {client_id}")
        try:
            while True:
                message = self.protocol_handler.receive(conn)
                if not message:
                    print(f"[-] Client disconnected: {client_id}")
                    break

                # Put the incoming message into the client's job queue
                self.client_queues[client_id].put(message)

                # Process whatever is in the queue
                                # this may need to be locked so that the server doesnt process multiple job q at the same time
                # maybe we need a lock on handle_client so multiple threads dont try to handle different clients at the same time.
                self.process_job_queue(client_id, conn)

        except Exception as e:
            print(f"Error handling {client_id}: {e}")
        finally:
            conn.close()
            # Clean up the client's queue if you want
            if client_id in self.client_queues:
                del self.client_queues[client_id]
            if client_id in self.logged_in_users:
                del self.logged_in_users[client_id]

    def process_job_queue(self, client_id, conn):
        """
        Process all pending jobs in the queue for this client.
        """
        queue = self.client_queues[client_id]

        while not queue.empty():
            job = queue.get()
            self.process_client_action(client_id, job, conn)

    def process_client_action(self, client_id, message: Message, conn):
        """
        Coarse-grained lock:
          We lock during this entire method so that only one thread can
          perform an action at a time, preventing DB concurrency issues.
        """
        with self.server_lock:
            msg_type = message.msg_type
            data = message.data
            if msg_type == "signup":
                self._action_signup(client_id, data, conn)
            elif msg_type == "login":
                self._action_login(client_id, data, conn)
            elif msg_type == "send_message":
                self._action_send_message(client_id, data, conn)
            elif msg_type == "fetch_messages":
                self._action_fetch_messages(client_id, data, conn)
            elif msg_type == "logout":
                self._action_logout(client_id, data, conn)
            elif msg_type == "send_delivered_messages":
                self._action_send_delivered_messages(client_id, data, conn)
            elif msg_type == "delete_messages":
                self._action_delete_messages(client_id, data, conn)
            elif msg_type == "reset_db":
                self._action_reset_db(client_id, data, conn)
            else:
                response_data = {"status": "error", "msg": f"Unknown action: {msg_type}"}
                self.protocol_handler.send(conn, Message("response", response_data))

    #############################
    # 4. ACTION METHODS
    #############################

    def _action_signup(self, client_id, data, conn):
        username = data.get("username")
        password_hash = data.get("password")  # hashed by client

        if not username or not password_hash:
            response_data = {"status": "error", "msg": "Invalid signup data."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        c = self.conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        row = c.fetchone()
        if row:
            response_data = {"status": "error", "msg": "Username already taken."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        c.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        self.conn.commit()
        response_data = {"status": "ok", "msg": "Signup successful. Please login."}
        self.protocol_handler.send(conn, Message("response", response_data))

    def _action_login(self, client_id, data, conn):
        username = data.get("username")
        password_hash = data.get("password")

        # no login info given
        if not username or not password_hash:
            response_data = {"status": "error", "msg": "Invalid login data."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        # 1. Check if user is already logged in by *any* client
        #    We'll look in self.logged_in_users.values().
        if username in self.logged_in_users.values():
            response_data = {"status": "error", "msg": "This user is already logged in."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        # 2. Check if *this* client is already logged in as a different user
        #    We only allow one account per client.
        if client_id in self.logged_in_users:
            current_user = self.logged_in_users[client_id]
            if current_user != username:
                response_data = {"status": "error", "msg": "Client is already logged in with another user."}
                self.protocol_handler.send(conn, Message("response", response_data))
                return

        c = self.conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        row = c.fetchone()

        # username not found
        if not row:
            response_data = {"status": "error", "msg": "Username not found."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        stored_hash = row[0]
        # password not correct
        if stored_hash != password_hash:
            response_data = {"status": "error", "msg": "Wrong password."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        # If correct
        self.logged_in_users[client_id] = username

        # Count unread
        c.execute("SELECT COUNT(*) FROM messages WHERE recipient=? AND delivered=0", (username,))
        (unread_count,) = c.fetchone()

        response_data = {
            "status": "ok",
            "msg": "Login successful.",
            "unread_count": unread_count
        }
        self.protocol_handler.send(conn, Message("response", response_data))

    def _action_send_message(self, client_id, data, conn):
        sender = data.get("sender")
        recipient = data.get("recipient")
        content = data.get("content")

        current_user = self.logged_in_users.get(client_id)
        if current_user != sender:
            response_data = {"status": "error", "msg": "You are not logged in as this sender."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        if not recipient or not content:
            response_data = {"status": "error", "msg": "Recipient and content required."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        c = self.conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (recipient,))
        user_row = c.fetchone()
        if not user_row:
            response_data = {"status": "error", "msg": "Recipient does not exist."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        self._store_message(sender, recipient, content)
        response_data = {"status": "ok", "msg": "message stored"}
        self.protocol_handler.send(conn, Message("response", response_data))

    def _action_fetch_messages(self, client_id, data, conn):
        num_messages = data.get("num_messages", 5)
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            response_data = {"status": "error", "msg": "You are not logged in."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return

        c = self.conn.cursor()
        c.execute(
            "SELECT id, sender, content FROM messages WHERE recipient=? AND delivered=0 ORDER BY id ASC LIMIT ?",
            (current_user, num_messages)
        )
        rows = c.fetchall()

        # Mark as delivered
        message_ids = [str(r[0]) for r in rows]
        if message_ids:
            placeholders = ",".join(["?"] * len(message_ids))
            query = f"UPDATE messages SET delivered=1 WHERE id IN ({placeholders})"
            c.execute(query, message_ids)
            self.conn.commit()

        fetched_messages = []
        for r in rows:
            msg_id, sndr, content = r
            fetched_messages.append({"id": msg_id, "sender": sndr, "content": content})

        response_data = {"status": "ok", "messages": fetched_messages}
        self.protocol_handler.send(conn, Message("response", response_data))


    def _action_logout(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            response_data = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return
        del self.logged_in_users[client_id]
        response_data = {"status": "ok", "msg": "You have been logged out."}
        self.protocol_handler.send(conn, Message("response", response_data))

    def _action_send_delivered_messages(self, client_id, data, conn):
        """
        Return all messages that have been delivered (delivered=1) for the logged-in user.
        """
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            response_data = {"status": "error", "msg": "You are not logged in."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return
        c = self.conn.cursor()
        c.execute(
            "SELECT id, sender, content FROM messages WHERE recipient=? AND delivered=1 ORDER BY id ASC",
            (current_user,)
        )
        rows = c.fetchall()
        delivered_list = []
        for r in rows:
            msg_id, sndr, content = r
            delivered_list.append({"id": msg_id, "sender": sndr, "content": content})
        response_data = {"status": "ok", "messages": delivered_list}
        self.protocol_handler.send(conn, Message("response", response_data))

    def _action_delete_messages(self, client_id, data, conn):
        """
        Delete one or more messages by ID. Only if recipient == current_user.
        data should have an array of message_ids_to_delete.
        """
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            response_data = {"status": "error", "msg": "You are not logged in."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return
        message_ids = data.get("message_ids_to_delete", [])
        if not isinstance(message_ids, list) or not message_ids:
            response_data = {"status": "error", "msg": "No valid message IDs provided."}
            self.protocol_handler.send(conn, Message("response", response_data))
            return
        c = self.conn.cursor()
        placeholders = ",".join(["?"] * len(message_ids))
        query = f"DELETE FROM messages WHERE id IN ({placeholders}) AND recipient=?"
        params = message_ids + [current_user]
        c.execute(query, params)
        deleted_count = c.rowcount
        self.conn.commit()
        response_data = {
            "status": "ok",
            "msg": f"Deleted {deleted_count} messages.",
            "deleted_count": deleted_count
        }
        self.protocol_handler.send(conn, Message("response", response_data))

    def _action_reset_db(self, client_id, data, conn):
        """Resets the database. TEMPORARY FEATURE for testing only."""
        print("⚠️ Resetting database upon client request...")
        c = self.conn.cursor()
        # Drop tables to clear old data
        c.execute("DROP TABLE IF EXISTS users;")
        c.execute("DROP TABLE IF EXISTS messages;")

        # Recreate tables
        c.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)

        c.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                recipient TEXT,
                content TEXT,
                delivered INTEGER DEFAULT 0
            );
        """)

        self.conn.commit()
        print("✅ Database reset complete.")
        response_data = {"status": "ok", "msg": "Database reset."}
        self.protocol_handler.send(conn, Message("response", response_data))

    #############################
    # 4. UTILITIES
    #############################

    def _store_message(self, sender, recipient, content):
        """
        Insert a message record into the SQLite DB.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages (sender, recipient, content, delivered)
            VALUES (?, ?, ?, ?)
            """,
            (sender, recipient, content, 0),
        )
        self.conn.commit()

if __name__ == "__main__":
    # Example usage: start in JSON mode
    server = Server(protocol="json")
    server.start_server()
