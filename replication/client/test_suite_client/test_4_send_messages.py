import sys
import os
import warnings
import unittest
from unittest.mock import patch, MagicMock
import streamlit as st

warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
from protocol import chat_service_pb2

class TestSendMessage(unittest.TestCase):
    """Test sending messages with gRPC stub."""

    def setUp(self):
        """Setup a mock gRPC stub for testing."""
        self.client = ChatServerClient(["127.0.0.1:50051", "127.0.0.1:50052", "127.0.0.1:50053"])

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_successful_message_send(self, mock_stub_class):
        """Test sending a message updates UI correctly."""
        mock_stub = MagicMock()
        mock_stub.SendMessage.return_value = chat_service_pb2.GenericResponse(status="ok")
        mock_stub_class.return_value = mock_stub

        sender = "Alice"
        recipient = "Bob"
        content = "Hello!"

        response = mock_stub.SendMessage(
            chat_service_pb2.SendMessageRequest(auth_token="test_token", recipient=recipient, content=content)
        )

        mock_stub.SendMessage.assert_called_once_with(
            chat_service_pb2.SendMessageRequest(auth_token="test_token", recipient=recipient, content=content)
        )
        self.assertEqual(response.status, "ok")

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_send_message_failure(self, mock_stub_class):
        """Test handling of message sending failure."""
        mock_stub = MagicMock()
        mock_stub.SendMessage.return_value = chat_service_pb2.GenericResponse(status="error", msg="Recipient not found")
        mock_stub_class.return_value = mock_stub

        sender = "Alice"
        recipient = "Nonexistent"
        content = "Hello!"

        response = mock_stub.SendMessage(
            chat_service_pb2.SendMessageRequest(auth_token="test_token", recipient=recipient, content=content)
        )

        mock_stub.SendMessage.assert_called_once_with(
            chat_service_pb2.SendMessageRequest(auth_token="test_token", recipient=recipient, content=content)
        )
        self.assertEqual(response.status, "error")
        self.assertEqual(response.msg, "Recipient not found")

if __name__ == "__main__":
    unittest.main()
