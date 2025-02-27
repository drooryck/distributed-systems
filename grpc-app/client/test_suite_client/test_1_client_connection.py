import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from client import ChatServerClient
import chat_service_pb2

class TestClientConnection(unittest.TestCase):
    """Test client interactions with the gRPC server."""

    def setUp(self):
        """Mock gRPC stub for testing."""
        self.client = ChatServerClient(server_host="127.0.0.1", server_port=50051)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_successful_login(self, mock_stub_class):
        """Test login flow with mocked gRPC response."""
        mock_stub = MagicMock()
        mock_stub.Login.return_value = chat_service_pb2.LoginResponse(
            status="ok", auth_token="test_token", unread_count=5
        )
        mock_stub_class.return_value = mock_stub

        username = "testuser"
        password = "password"
        hashed_pw = self.client.hash_password(password)

        response = mock_stub.Login(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))

        mock_stub.Login.assert_called_once_with(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.auth_token, "test_token")
        self.assertEqual(response.unread_count, 5)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_failed_login(self, mock_stub_class):
        """Test failed login attempt."""
        mock_stub = MagicMock()
        mock_stub.Login.return_value = chat_service_pb2.LoginResponse(status="error", auth_token="", unread_count=0)
        mock_stub_class.return_value = mock_stub

        username = "unknown_user"
        password = "wrong_password"
        hashed_pw = self.client.hash_password(password)

        response = mock_stub.Login(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))

        mock_stub.Login.assert_called_once_with(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))
        self.assertEqual(response.status, "error")
        self.assertEqual(response.auth_token, "")
        self.assertEqual(response.unread_count, 0)

if __name__ == "__main__":
    unittest.main()
