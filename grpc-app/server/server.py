import grpc
from concurrent import futures
import chat_service_pb2
import chat_service_pb2_grpc

import secrets

from database import Database  # ✅ Import your database class

class ChatServiceServicer(chat_service_pb2_grpc.ChatServiceServicer):
    def __init__(self, db, logged_in_users):
        self.db = db 
        self.logged_in_users = logged_in_users

    def Signup(self, request, context):
        """Handles user signup requests."""
        username, password = request.username, request.password

        # i want to deprecate this, i want client to handle this. comment out soon!!!
        if not username or not password:
            return chat_service_pb2.GenericResponse(
                status="error",
                msg="Username and password are required"
            )
        
        # Check if the username exists
        result = self.db.execute("SELECT id FROM users WHERE username=?", (username,))
        if result:
            return chat_service_pb2.GenericResponse(
                status="error",
                msg="Username already taken"
            )

        self.db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password), commit=True)
        
        return chat_service_pb2.GenericResponse(
            status="ok",
            msg="Signup successful"
        )


    def Login(self, request, context):
        """Handles user login requests."""
        username, password = request.username, request.password

        # missing data
        if not username or not password:
            return chat_service_pb2.GenericResponse(
                status="error",
                msg="Username and password are required"
            )
        
        # user already logged in by any client
        if username in self.logged_in_users.values():
            return chat_service_pb2.GenericResponse(
                status="error",
                msg="User already logged in"
            )
        
        # we cant check if the client is logged in as someone else
        # the auth_token they are using deifnes who they are logged in as
        # they could use two auth tokens in two messages and act like 2 users.

        
        row = self.db.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        # username not found
        if not row:
            return chat_service_pb2.GenericResponse(
                status="error",
                msg="Username not found"
            )
        
        stored_hash = row[0][0]
        # incorrect password
        if stored_hash != password:
            return chat_service_pb2.GenericResponse(
                status="error",
                msg="Incorrect password"
            )
        
        # get an auth token
        auth_token = secrets.token_hex(16)
        self.logged_in_users[auth_token] = username
        
        # get the unread count

        unread_count = self.db.execute("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE recipient=? AND to_deliver=0
        """, (username,))[0][0]
        unread_count = unread_count[0][0] if unread_count else 0
    

        # now we are fine
        return chat_service_pb2.LoginResponse(
            status="ok",
            msg="Login successful",
            auth_token=auth_token, # important! and client will need this
            unread_count=unread_count  # Example data, should come from DB
        )

    def Logout(self, request, context):
        """Handles user logout."""
    
        if request.auth_token not in self.logged_in_users:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
        
        del self.logged_in_users[request.auth_token]

        return chat_service_pb2.GenericResponse(
            status="ok",
            msg="You have been logged out."
        )

def serve():
    db = Database("chat.db")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(
        ChatServiceServicer(db=db, logged_in_users={}),
        server
    )
    server.add_insecure_port("[::]:50051")
    print("Starting gRPC server on port 50051...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
