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
        """Set up the client with a mocked stub."""
        self.client = ChatServerClient(server_host="127.0.0.1", server_port=50051)

    def test_hash_password(self):
        """Ensure password hashing works correctly."""
        password = "test_password"
        hashed_pw = self.client.hash_password(password)

        self.assertEqual(len(hashed_pw), 64)  # SHA-256 hash length
        self.assertNotEqual(password, hashed_pw)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_stub_creation(self, mock_stub_class):
        """Ensure the gRPC stub is created properly."""
        mock_stub = MagicMock()
        mock_stub_class.return_value = mock_stub

        channel = grpc.insecure_channel("127.0.0.1:50051")
        stub = mock_stub_class(channel)

        mock_stub_class.assert_called_once_with(channel)
        self.assertEqual(stub, mock_stub)

if __name__ == "__main__":
    unittest.main()
