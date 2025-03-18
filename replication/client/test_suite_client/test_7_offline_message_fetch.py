import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
import chat_service_pb2

class TestOfflineMessageFetch(unittest.TestCase):
    """Test manual fetching of offline messages."""

    def setUp(self):
        """Set up a ChatServerClient instance."""
        self.client = ChatServerClient(server_host="127.0.0.1", server_port=50051)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_manual_fetch_offline_messages(self, mock_stub_class):
        """Test that manually fetching offline messages retrieves the correct data."""
        st.session_state.clear()

        mock_stub = MagicMock()
        mock_stub.FetchAwayMsgs.return_value = chat_service_pb2.ListMessagesResponse(
            status="ok",
            msg="Offline messages retrieved",
            messages=[
                chat_service_pb2.ChatMessage(id=202, sender="Alice", content="Offline message")
            ],
            total_count=1
        )
        mock_stub_class.return_value = mock_stub

        response = mock_stub.FetchAwayMsgs(
            chat_service_pb2.FetchAwayMsgsRequest(auth_token="test_token", limit=5)
        )

        mock_stub.FetchAwayMsgs.assert_called_once_with(
            chat_service_pb2.FetchAwayMsgsRequest(auth_token="test_token", limit=5)
        )
        self.assertEqual(response.status, "ok")

        retrieved_messages = [{"id": m.id, "sender": m.sender, "content": m.content} for m in response.messages]

        self.assertEqual(len(retrieved_messages), 1)
        self.assertEqual(retrieved_messages[0]["id"], 202)

if __name__ == "__main__":
    unittest.main(verbosity=2)
