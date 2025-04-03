import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import grpc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient

class BaseTestClient(unittest.TestCase):
    """Base test case for client-side functionality."""

    def setUp(self):
        """
        Initialize the ChatServerClient with a list of server addresses.
        Adjust as needed for your environment/test scenario.
        """
        self.client = ChatServerClient(["127.0.0.1:50051", "127.0.0.1:50052", "127.0.0.1:50053"])

    def test_hash_password(self):
        """Ensure password hashing works correctly (SHA-256)."""
        password = "test_password"
        hashed_pw = self.client.hash_password(password)

        # SHA-256 hex digest is 64 characters long
        self.assertEqual(len(hashed_pw), 64, "Hashed password should be 64 hex characters")
        self.assertNotEqual(password, hashed_pw, "Plain text should differ from the hash")

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_stub_creation(self, mock_stub_class):
        """
        Verify that a gRPC stub is created when the client attempts an RPC call.
        We mock ChatServiceStub to ensure we're not making real network calls.
        """
        mock_stub_instance = MagicMock()
        mock_stub_class.return_value = mock_stub_instance

        # Trigger a client call that internally creates a stub & channel
        # For example, 'signup' is a method that calls _try_stub_call(...)
        self.client.signup("testuser", "hashedpw123")

        # Ensure ChatServiceStub was indeed constructed at least once
        self.assertTrue(mock_stub_class.called, "ChatServiceStub was not created as expected.")
        

if __name__ == "__main__":
    unittest.main()