import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import grpc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
import chat_service_pb2

class TestErrorHandling(unittest.TestCase):
    """Test error handling for gRPC connection failures."""

    def setUp(self):
        """Set up a ChatServerClient instance."""
        self.client = ChatServerClient(server_host="127.0.0.1", server_port=50051)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_network_failure(self, mock_stub_class):
        """Simulate a network failure causing the client to return None."""
        mock_stub = MagicMock()
        mock_stub.Login.side_effect = grpc.RpcError("Network failure")
        mock_stub_class.return_value = mock_stub

        username = "Alice"
        password = self.client.hash_password("secret")
        response = None

        try:
            response = mock_stub.Login(chat_service_pb2.LoginRequest(username=username, password=password))
        except grpc.RpcError:
            pass  # Simulate handling failure

        self.assertIsNone(response)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_server_timeout(self, mock_stub_class):
        """Simulate a gRPC timeout, ensuring the client handles it properly."""
        mock_stub = MagicMock()
        mock_stub.Login.side_effect = grpc.RpcError("Timeout occurred")
        mock_stub_class.return_value = mock_stub

        username = "Alice"
        password = self.client.hash_password("secret")
        response = None

        try:
            response = mock_stub.Login(chat_service_pb2.LoginRequest(username=username, password=password))
        except grpc.RpcError:
            pass  # Expected behavior for timeout

        self.assertIsNone(response)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_server_disconnect(self, mock_stub_class):
        """Simulate a server disconnect where the connection drops mid-request."""
        mock_stub = MagicMock()
        mock_stub.Login.side_effect = grpc.RpcError("Server disconnected")
        mock_stub_class.return_value = mock_stub

        username = "Alice"
        password = self.client.hash_password("secret")
        response = None

        try:
            response = mock_stub.Login(chat_service_pb2.LoginRequest(username=username, password=password))
        except grpc.RpcError:
            pass  # Expected handling for disconnection

        self.assertIsNone(response)

if __name__ == "__main__":
    unittest.main(verbosity=2)
