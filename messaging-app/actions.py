from protocol import Message


#############################
# ACTION METHODS (ORDERED)
#############################
class ActionHandler:
    def __init__(self, db, protocol_handler, logged_in_users):
        self.db = db
        self.protocol_handler = protocol_handler
        self.logged_in_users = logged_in_users

    def process_client_action(self, client_id, message: Message, conn):
        action_map = {
            "signup": self._action_signup,
            "login": self._action_login,
            "logout": self._action_logout,
            "send_message": self._action_send_message,
            "count_unread": self._action_count_unread,
            "send_messages_to_client": self._action_send_messages_to_client,
            "fetch_away_msgs": self._action_fetch_away_messages,
            "list_accounts": self._action_list_accounts,
            "delete_messages": self._action_delete_messages,
            "delete_account": self._action_delete_account,
            "reset_db": self._action_reset_db
        }
        action = action_map.get(message.msg_type)
        if action:
            action(client_id, message.data, conn)
        else:
            self.protocol_handler.send(conn, Message("signup", {"status": "error", "msg": "Unknown action"}), is_response=1)

    # 1) signup
    def _action_signup(self, client_id, data, conn):
        username, password = data.get("username"), data.get("password")
        if not username or not password:
            self.protocol_handler.send(conn, Message("signup", {"status": "error", "msg": "Invalid data"}), is_response=1)
            return
        
        result = self.db.execute("SELECT id FROM users WHERE username=?", (username,))
        if result:
            self.protocol_handler.send(conn, Message("signup", {"status": "error", "msg": "Username taken"}), is_response=1)
            return

        self.db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password), commit=True)
        self.protocol_handler.send(conn, Message("signup", {"status": "ok", "msg": "Signup successful"}), is_response=1)


    # 2) login
    def _action_login(self, client_id, data, conn):
        username = data.get("username")
        password_hash = data.get("password")
        if not username or not password_hash:
            resp = {"status": "error", "msg": "Invalid login data."}
            self.protocol_handler.send(conn, Message("login", resp), is_response=1)
            return

        # Already logged in by any client?
        if username in self.logged_in_users.values():
            resp = {"status": "error", "msg": "This user is already logged in."}
            self.protocol_handler.send(conn, Message("login", resp), is_response=1)
            return

        # This client is already logged in as another user?
        if client_id in self.logged_in_users:
            current_user = self.logged_in_users[client_id]
            if current_user != username:
                resp = {"status": "error", "msg": "Client is already logged in with another user."}
                self.protocol_handler.send(conn, Message("login", resp), is_response=1)
                return

        row = self.db.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        if not row:
            resp = {"status": "error", "msg": "Username not found."}
            self.protocol_handler.send(conn, Message("login", resp), is_response=1)
            return

        stored_hash = row[0][0]
        if stored_hash != password_hash:
            resp = {"status": "error", "msg": "Wrong password."}
            self.protocol_handler.send(conn, Message("login", resp), is_response=1)
            return

        # Login success
        self.logged_in_users[client_id] = username
        # im not going to use the count action here because i dont want too many dependencies of actions on other actions.
        unread_count = self.db.execute("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE recipient=? AND to_deliver=0
        """, (username,))

        resp = {
            "status": "ok",
            "msg": "Login successful.",
            "unread_count": unread_count[0][0]
        }
        self.protocol_handler.send(conn, Message("login", resp), is_response=1)

    # 3) logout
    def _action_logout(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("logout", resp), is_response=1)
            return
        del self.logged_in_users[client_id]
        resp = {"status": "ok", "msg": "You have been logged out."}
        self.protocol_handler.send(conn, Message("logout", resp), is_response=1)

    # 4) count_unread
    def _action_count_unread(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("count_unread", resp), is_response=1)
            return

        result = self.db.execute("""
            SELECT COUNT(*) 
            FROM messages
            WHERE recipient=? AND to_deliver=0
        """, (current_user,))
        
        unread_count = result[0][0] if result else 0  # Handle empty result

        resp = {
            "status": "ok",
            "msg": "Count of away messages.",
            "unread_count": unread_count
        }
        self.protocol_handler.send(conn, Message("count_unread", resp), is_response=1)

    # 5) send_message
    def _action_send_message(self, client_id, data, conn):
        sender = data.get("sender")
        recipient = data.get("recipient")
        content = data.get("content")

        # on a decoding bug...
        if not sender or not recipient or not content:
            resp = {"status": "error", "msg": "Sender, recipient, and content required."}
            self.protocol_handler.send(conn, Message("send_message", resp), is_response=1)
            return

        current_user = self.logged_in_users.get(client_id)
        if current_user != sender:
            resp = {"status": "error", "msg": "You are not logged in as this sender."}
            self.protocol_handler.send(conn, Message("send_message", resp), is_response=1)
            return

        row = self.db.execute("SELECT id FROM users WHERE username=?", (recipient,))
        if not row:
            resp = {"status": "error", "msg": "Recipient does not exist."}
            self.protocol_handler.send(conn, Message("send_message", resp), is_response=1)
            return

        # If the recipient is logged in, we mark to_deliver=1 immediately
        recipient_is_logged_in = any(u == recipient for u in self.logged_in_users.values())
        delivered_value = 1 if recipient_is_logged_in else 0

        # Insert into messages with to_deliver=(0 or 1)
        self.db.execute("""
            INSERT INTO messages (sender, recipient, content, to_deliver)
            VALUES (?, ?, ?, ?)
        """, (sender, recipient, content, delivered_value))

        resp = {"status": "ok", "msg": "Message stored."}
        self.protocol_handler.send(conn, Message("send_message", resp), is_response=1)


    # 6) send_messages_to_client
    #    - returns any messages that are to be delivered (to_deliver==1), marking them delivered=1.
    def _action_send_messages_to_client(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("send_messages_to_client", resp), is_response=1)
            return

        rows = self.db.execute("""
            SELECT id, sender, content, to_deliver
            FROM messages
            WHERE recipient=? AND to_deliver=1
            ORDER BY id ASC
        """, (current_user,))

        results = []
        for (msg_id, snd, content, to_deliver) in rows:
            results.append({
                "id": msg_id,
                "sender": snd,
                "content": content,
                "to_deliver": to_deliver
            })

        resp = {"status": "ok", "msg": results}
        self.protocol_handler.send(conn, Message("send_messages_to_client", resp), is_response=1)

    # 7) fetch_away_messages
    #    - returns a specified number of messages that have to_deliver==0
    #    - doesn't even need to send anything back to be honest.
    def _action_fetch_away_messages(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("fetch_away_msgs", resp), is_response=1)
            return
        
        limit = data.get("limit")

        if not limit:
            resp = {"status": "error", "msg": "No limit specified."}
            self.protocol_handler.send(conn, Message("fetch_away_msgs", resp), is_response=1)


        # Find messages that have not been delivered yet
        rows = self.db.execute("""
            SELECT id, sender, content
            FROM messages
            WHERE recipient=? AND to_deliver=0
            ORDER BY id ASC
            LIMIT ?
        """, (current_user, limit))

        # Mark them delivered
        message_ids = [str(r[0]) for r in rows]
        if message_ids:
            placeholders = ",".join(["?"] * len(message_ids))
            query = f"UPDATE messages SET to_deliver=1 WHERE id IN ({placeholders})"
            self.db.execute(query, message_ids)

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
        self.protocol_handler.send(conn, Message("fetch_away_msgs", resp), is_response=1)


    # 8) list_accounts
    def _action_list_accounts(self, client_id, data, conn):
        # Check for pattern key and nonempty pattern.
        pattern = data.get("pattern")
        if pattern is None or pattern == "":
            resp = {"status": "error", "msg": "No pattern provided."}
            self.protocol_handler.send(conn, Message("list_accounts", resp), is_response=1)
            return

        # Build the SQL search pattern.
        sql_pattern = f"%{pattern}%"
        try:
            start = int(data.get("start", 0))
            count = int(data.get("count", 10))
        except (ValueError, TypeError):
            resp = {"status": "error", "msg": "Invalid pagination parameters."}
            self.protocol_handler.send(conn, Message("list_accounts", resp), is_response=1)
            return

        # Inline the LIMIT and OFFSET values into the query string.
        query = f"""
            SELECT id, username 
            FROM users 
            WHERE username LIKE ?
            ORDER BY username 
            LIMIT {count} OFFSET {start}
        """
        rows = self.db.execute(query, (sql_pattern,)) or []

        # Build a list of (id, username) tuples.
        matched = [(row[0], row[1]) for row in rows]

        # Send response with status ok.
        resp = {"status": "ok", "users": matched}
        self.protocol_handler.send(conn, Message("list_accounts", resp), is_response=1)

    # 9) delete_messages
    def _action_delete_messages(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not logged in."}
            self.protocol_handler.send(conn, Message("delete_messages", resp), is_response=1)
            return

        message_ids = data.get("message_ids_to_delete", [])
        if not isinstance(message_ids, list) or not message_ids:
            resp = {"status": "error", "msg": "No valid message IDs provided."}
            self.protocol_handler.send(conn, Message("delete_messages", resp), is_response=1)
            return

        placeholders = ",".join(["?"] * len(message_ids))
        query = f"DELETE FROM messages WHERE id IN ({placeholders}) AND recipient=?"
        params = message_ids + [current_user]

        deleted_count = self.db.execute(query, params, commit=True)

        resp = {
            "status": "ok",
            "msg": f"Deleted {deleted_count} messages.",
            "deleted_count": deleted_count
        }
        self.protocol_handler.send(conn, Message("delete_messages", resp), is_response=1)


    # 10) delete_account
    def _action_delete_account(self, client_id, data, conn):
        current_user = self.logged_in_users.get(client_id)
        if not current_user:
            resp = {"status": "error", "msg": "You are not currently logged in."}
            self.protocol_handler.send(conn, Message("delete_account", resp), is_response=1)
            return

        # Delete all messages from AND to this user
        self.db.execute("DELETE FROM messages WHERE sender=? OR recipient=?", (current_user, current_user))
        # Delete the user record
        self.db.execute("DELETE FROM users WHERE username=?", (current_user,))

        del self.logged_in_users[client_id]
        resp = {
            "status": "ok",
            "msg": f"Account has been deleted. All associated messages are removed."
        }
        self.protocol_handler.send(conn, Message("delete_account", resp), is_response=1)

    # 11) reset_db
    def _action_reset_db(self, client_id, data, conn):
        # print("Resetting database upon client request...")
        self.db.execute("DROP TABLE IF EXISTS users;")
        self.db.execute("DROP TABLE IF EXISTS messages;")

        self.db.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                recipient TEXT,
                content TEXT,
                to_deliver INTEGER DEFAULT 0
            );
        """)

        resp = {"status": "ok", "msg": "Database reset."}
        self.protocol_handler.send(conn, Message("reset_db", resp), is_response=1)