import grpc
from concurrent import futures
from multiprocessing import Manager
import secrets
import argparse

from database import Database  # ✅ Import your database class

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import chat_service_pb2
import chat_service_pb2_grpc

class ChatServiceServicer(chat_service_pb2_grpc.ChatServiceServicer):
    def __init__(self, db, logged_in_users, is_primary=False, backup_addresses=None):
        self.db = db
        self.logged_in_users = logged_in_users
        self.is_primary = is_primary
        self.backup_addresses = backup_addresses or []

    def replicate_to_backups(self, op_type, **kwargs):
        # For each backup address, call a "Replicate" RPC.
        for addr in self.backup_addresses:
            try:
                channel = grpc.insecure_channel(addr)
                stub = chat_service_pb2_grpc.ChatServiceStub(channel)

                req = chat_service_pb2.ReplicationRequest(op_type=op_type)

                if "sender" in kwargs:
                    req.sender = kwargs["sender"]
                if "recipient" in kwargs:
                    req.recipient = kwargs["recipient"]
                if "content" in kwargs:
                    req.content = kwargs["content"]
                if "message_ids" in kwargs:
                    req.message_ids.extend(kwargs["message_ids"])

                stub.Replicate(req)
            except Exception as e:
                print(f"[Primary] Failed to replicate to {addr}: {e}")

    def Replicate(self, request, context):
        op_type = request.op_type
        if op_type == "INSERT_MESSAGE":
            self.db.execute(
                """INSERT INTO messages (sender, recipient, content, to_deliver)
                   VALUES (?, ?, ?, ?)""",
                (request.sender, request.recipient, request.content, 1),
                commit=True
            )
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated insert")

        elif op_type == "DELETE_MESSAGES":
            placeholders = ",".join(["?" for _ in request.message_ids])
            self.db.execute(
                f"DELETE FROM messages WHERE id IN ({placeholders})",
                tuple(request.message_ids),
                commit=True
            )
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated delete")

        elif op_type == "SIGNUP_USER":
            self.db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (request.sender, request.content),
                commit=True
            )
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated signup")

        elif op_type == "DELETE_ACCOUNT":
            user_to_del = request.sender
            self.db.execute(
                "DELETE FROM messages WHERE sender=? OR recipient=?",
                (user_to_del, user_to_del),
                commit=True
            )
            self.db.execute(
                "DELETE FROM users WHERE username=?",
                (user_to_del,),
                commit=True
            )
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated account delete")

        return chat_service_pb2.GenericResponse(status="error", msg="Unknown replication op_type")

    def Signup(self, request, context):
        """Handles user signup requests."""
        username, password = request.username, request.password

        # i want to deprecate this, i want client to handle this. comment out soon!!!
        if not username or not password:
            return chat_service_pb2.GenericResponse(status="error", msg="Username and password are required")
        
        # Check if the username exists
        result = self.db.execute("SELECT id FROM users WHERE username=?", (username,), commit=True)
        if result:
            return chat_service_pb2.GenericResponse(status="error", msg="Username already taken")

        self.db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password), commit=True)
        
        if self.is_primary:
            self.replicate_to_backups(
                "SIGNUP_USER",
                sender=username,
                content=password
            )
        
        return chat_service_pb2.GenericResponse(status="ok", msg="Signup successful")

    def Login(self, request, context):
        """Handles user login requests."""
        username, password = request.username, request.password

        # missing data
        if not username or not password:
            return chat_service_pb2.GenericResponse(status="error", msg="Username and password are required")
        
        # user already logged in by any client
        # handle this by logging out the old client with their auth token and given a new one (#mog)
        for tok, logged_in_username in self.logged_in_users.items():
            if logged_in_username == username:
                del self.logged_in_users[tok]
                break
        
        # we cant check if the client is logged in as someone else
        # the auth_token they are using deifnes who they are logged in as
        # they could use two auth tokens in two messages and act like 2 users.

        
        row = self.db.execute("SELECT password_hash FROM users WHERE username=?", (username,), commit=True)
        # username not found
        if not row:
            return chat_service_pb2.GenericResponse(status="error", msg="Username not found")
        
        stored_hash = row[0][0]
        # incorrect password
        if stored_hash != password:
            return chat_service_pb2.GenericResponse(status="error", msg="Incorrect password")
        
        # get an auth token
        auth_token = secrets.token_hex(16)
        self.logged_in_users[auth_token] = username
        
        # get the unread count
        rows = self.db.execute("""SELECT COUNT(*) FROM messages WHERE recipient=? AND to_deliver=0""", (username,), commit=True)
        unread_count = rows[0][0] if rows else 0  # Handle empty result

        # now we are fine
        # important! and client will need the auth token
        return chat_service_pb2.LoginResponse(status="ok", msg="Login successful", auth_token=auth_token, unread_count=unread_count)

    def Logout(self, request, context):
        """Handles user logout."""
    
        if request.auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
        
        del self.logged_in_users[request.auth_token]

        return chat_service_pb2.GenericResponse(status="ok", msg="You have been logged out.")
    
    def CountUnread(self, request, context):
        """Handles unread message count requests."""

        if request.auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")

        result = self.db.execute(""" SELECT COUNT(*) FROM messages WHERE recipient=? AND to_deliver=0 """, (self.logged_in_users[request.auth_token],), commit=True)

        unread_count = result[0][0] if result else 0  # Handle empty result

        return chat_service_pb2.CountUnreadResponse(status="ok", msg="Unread count fetched", unread_count=unread_count)

    def SendMessage(self, request, context):
        content, auth_token = request.content, request.auth_token
        sender = self.logged_in_users.get(auth_token, -1)
        if sender == -1:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
        
        result = self.db.execute("SELECT username FROM users WHERE username=?", (request.recipient,), commit=True)
        if not result:
            return chat_service_pb2.GenericResponse(status="error", msg="Recipient not found")
        recipient = result[0][0]
        delivered_value = 1 if recipient in self.logged_in_users.values() else 0

        self.db.execute(""" INSERT INTO messages (sender, recipient, content, to_deliver) VALUES (?, ?, ?, ?) """, (sender, recipient, content, delivered_value), commit=True)

        if self.is_primary:
            self.replicate_to_backups(
                "INSERT_MESSAGE",
                sender=sender,
                recipient=recipient,
                content=content
            )

        return chat_service_pb2.GenericResponse(status="ok", msg="Message sent")
    
    def ListMessages(self, request, context):
        cur_user = self.logged_in_users.get(request.auth_token, -1)

        if request.auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
    
        # 2) Count how many messages the user has total
        row = self.db.execute(
            "SELECT COUNT(*) FROM messages WHERE recipient=?",
            (cur_user,)
        )
        total_count = row[0][0] if row else 0

        # 3) Get just the slice of messages for this page
        rows = self.db.execute("""SELECT id, sender, content, to_deliver FROM messages WHERE recipient=? ORDER BY id DESC LIMIT ? OFFSET ?""",(cur_user, request.count, request.start))

        # 4) Build the repeated ChatMessage
        messages = []
        for msg_id, sender, content, to_deliver in rows:
            cm = chat_service_pb2.ChatMessage(
                id=msg_id,
                sender=sender,
                content=content
            )
            messages.append(cm)

        return chat_service_pb2.ListMessagesResponse(
            status="ok",
            msg="Messages retrieved successfully",
            messages=messages,
            total_count=total_count
        )

    def FetchAwayMsgs(self, request, context):
        cur_user = self.logged_in_users.get(request.auth_token, -1)
        if request.auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
    

        # Find messages that have not been delivered yet
        rows = self.db.execute("""SELECT id, sender, content FROM messages WHERE recipient=? AND to_deliver=0 ORDER BY id ASC LIMIT ?""", (cur_user, request.limit), commit=True)
        if rows:
            self.db.execute("""UPDATE messages SET to_deliver=1 WHERE id IN ({})""".format(','.join('?' * len(rows))), tuple(row[0] for row in rows), commit=True)

        # Convert to ChatMessage format and return
        return chat_service_pb2.ListMessagesResponse(
            status="ok",
            msg="Messages retrieved successfully",
            messages=[chat_service_pb2.ChatMessage(id=msg_id, sender=sender, content=content) for msg_id, sender, content in rows]
        )
    
    def ListAccounts(self, request, context):
        pattern, auth_token, start, count = request.pattern, request.auth_token, request.start, request.count
        if auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
        
        sql_pattern = f"%{pattern}%"  # SQL pattern for LIKE queries
        rows = self.db.execute("SELECT id, username FROM users WHERE username LIKE ? LIMIT ? OFFSET ?", (sql_pattern, count, start), commit=True)

        # Convert rows to UserRecord messages
        user_records = [
            chat_service_pb2.UserRecord(id=row[0], username=row[1])
            for row in rows
        ]

        return chat_service_pb2.ListAccountsResponse(status="ok", msg="Accounts retrieved successfully", users=user_records)

    def DeleteMessages(self, request, context):
        auth_token = request.auth_token
        if auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
        
        placeholders = ','.join(['?' for _ in request.message_ids_to_delete])
        
        self.db.execute(f"DELETE FROM messages WHERE recipient=? AND id IN ({placeholders})", [self.logged_in_users[auth_token]] + list(request.message_ids_to_delete), commit=True)

        if self.is_primary:
            self.replicate_to_backups(
                "DELETE_MESSAGES",
                message_ids=request.message_ids_to_delete
            )

        return chat_service_pb2.DeleteMessagesResponse(status="ok", msg="Messages deleted successfully", deleted_count=len(request.message_ids_to_delete))
        
    def DeleteAccount(self, request, context):
        auth_token = request.auth_token
        if auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
            
        username = self.logged_in_users[auth_token]
        self.db.execute("DELETE FROM messages WHERE sender=? OR recipient=?", (username, username), commit=True)
        self.db.execute("DELETE FROM users WHERE username=?", (username,), commit=True)
        del self.logged_in_users[auth_token]

        if self.is_primary:
            self.replicate_to_backups(
                "DELETE_ACCOUNT",
                sender=username
            )

        return chat_service_pb2.GenericResponse(status="ok", msg="Account deleted successfully")

    def ResetDB(self, request, context):
        auth_token = request.auth_token
        if auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
        
        self.db.execute("DROP TABLE IF EXISTS users", commit=True)
        self.db.execute("DROP TABLE IF EXISTS messages", commit=True)
        self.db._init_db()  # Reuse the initialization function

        return chat_service_pb2.GenericResponse(status="ok", msg="Database reset successfully")


def serve():
    parser = argparse.ArgumentParser(description="Chat Server with Replication")
    parser.add_argument("--port", type=int, default=50051, help="Port to listen on")
    parser.add_argument("--db_file", type=str, default="chat.db", help="SQLite DB file name")
    parser.add_argument("--role", type=str, default="primary", choices=["primary","backup"], help="primary or backup role")
    parser.add_argument("--backups", type=str, default="", help="Comma-separated backup addresses, only used if primary")
    args = parser.parse_args()

    db = Database(args.db_file)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(
        ChatServiceServicer(
            db=db,
            logged_in_users=Manager().dict(),
            is_primary=(args.role == "primary"),
            backup_addresses=[addr.strip() for addr in args.backups.split(",") if addr.strip()]
        ),
        server
    )

    listen_addr = f"[::]:{args.port}"
    server.add_insecure_port(listen_addr)
    print(f"Starting {args.role} server on port {args.port} with DB={args.db_file}")
    if args.role == "primary":
        print(f"Backups: {[addr.strip() for addr in args.backups.split(',') if addr.strip()]}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
