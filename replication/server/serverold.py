import grpc
from concurrent import futures
from multiprocessing import Manager
import secrets

from database import Database  # ✅ Import your database class

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

class ChatServiceServicer(chat_service_pb2_grpc.ChatServiceServicer):
    def __init__(self, db, logged_in_users):
        self.db = db 
        self.logged_in_users = logged_in_users

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

        return chat_service_pb2.DeleteMessagesResponse(status="ok", msg="Messages deleted successfully", deleted_count=len(request.message_ids_to_delete))
        
    def DeleteAccount(self, request, context):
        auth_token = request.auth_token
        if auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
            
        username = self.logged_in_users[auth_token]
        self.db.execute("DELETE FROM messages WHERE sender=? OR recipient=?", (username, username), commit=True)
        self.db.execute("DELETE FROM users WHERE username=?", (username,), commit=True)
        del self.logged_in_users[auth_token]

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
    db = Database("chat.db")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # we use a thread safe, but shared dictionary of auth-tokens->usernames
    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(
        ChatServiceServicer(db=db, logged_in_users=Manager().dict()),
        server
    )
    server.add_insecure_port("[::]:50051")
    print("Starting gRPC server on port 50051...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()