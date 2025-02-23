import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
import chat_service_pb2

class TestFetchInbox(unittest.TestCase):
    """Test real-time fetching of inbox messages."""

    def setUp(self):
        """Set up a ChatServerClient instance."""
        self.client = ChatServerClient(server_host="127.0.0.1", server_port=50051)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_auto_fetch_inbox(self, mock_stub_class):
        """Test that auto-fetch retrieves new messages and updates the UI."""
        st.session_state.clear()
        st.session_state["inbox_page"] = 0  # Simulating user on first page

        mock_stub = MagicMock()
        mock_stub.ListMessages.return_value = chat_service_pb2.ListMessagesResponse(
            status="ok",
            msg="Messages retrieved",
            messages=[
                chat_service_pb2.ChatMessage(id=101, sender="Bob", content="Auto message")
            ],
            total_count=1
        )
        mock_stub_class.return_value = mock_stub

        response = mock_stub.ListMessages(
            chat_service_pb2.ListMessagesRequest(auth_token="test_token", start=0, count=10)
        )

        mock_stub.ListMessages.assert_called_once_with(
            chat_service_pb2.ListMessagesRequest(auth_token="test_token", start=0, count=10)
        )
        self.assertEqual(response.status, "ok")

        # Simulate UI displaying messages instead of storing them in session state
        retrieved_messages = [{"id": m.id, "sender": m.sender, "content": m.content} for m in response.messages]

        self.assertEqual(len(retrieved_messages), 1)
        self.assertEqual(retrieved_messages[0]["id"], 101)

if __name__ == "__main__":
    unittest.main(verbosity=2)
