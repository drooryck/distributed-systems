import unittest
import grpc
import sys, os

# Ensure the correct import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import chat_service_pb2
import chat_service_pb2_grpc

SERVER_ADDRESS = "localhost:50051"

class BaseTest(unittest.TestCase):
    """Base test class that resets the database before each test and manages gRPC connections."""

    def setUp(self):
        """Initialize gRPC channel and stub before each test."""
        self.channel = grpc.insecure_channel(SERVER_ADDRESS)
        self.stub = chat_service_pb2_grpc.ChatServiceStub(self.channel)

        # Ensure admin exists and reset the database
        self.reset_database()

    def tearDown(self):
        """Close gRPC channel after each test."""
        self.channel.close()

    def reset_database(self):
        """Ensure the admin user exists, logs in, and resets the database using gRPC."""
        
        # Step 1: Try signing up the admin user (ignore if already exists)
        self.stub.Signup(chat_service_pb2.SignupRequest(username="admin", password="adminpass"))

        # Step 2: Log in as admin and get the auth token
        login_response = self.stub.Login(chat_service_pb2.LoginRequest(username="admin", password="adminpass"))
        if login_response.status != "ok":
            raise RuntimeError("Failed to log in as admin for database reset")

        # Step 3: Send ResetDB request with auth token
        reset_request = chat_service_pb2.EmptyRequest(auth_token=login_response.auth_token)
        self.stub.ResetDB(reset_request)
