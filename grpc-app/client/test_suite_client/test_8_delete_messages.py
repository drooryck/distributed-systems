import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
import chat_service_pb2

class TestDeleteMessages(unittest.TestCase):
    """Test message deletion behavior."""

    def setUp(self):
        """Set up a ChatServerClient instance."""
        self.client = ChatServerClient(server_host="127.0.0.1", server_port=50051)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_delete_selected_messages(self, mock_stub_class):
        """Test that deleting selected messages sends the correct request to the server."""
        st.session_state.clear()
        st.session_state["inbox_page"] = 0  # Simulating user on the first inbox page

        mock_stub = MagicMock()
        mock_stub.DeleteMessages.return_value = chat_service_pb2.DeleteMessagesResponse(
            status="ok", deleted_count=2
        )
        mock_stub_class.return_value = mock_stub

        # Simulate the deletion of messages with IDs 101 and 102
        message_ids_to_delete = [101, 102]
        response = mock_stub.DeleteMessages(
            chat_service_pb2.DeleteMessagesRequest(
                auth_token="test_token",
                message_ids_to_delete=message_ids_to_delete
            )
        )

        mock_stub.DeleteMessages.assert_called_once_with(
            chat_service_pb2.DeleteMessagesRequest(
                auth_token="test_token",
                message_ids_to_delete=message_ids_to_delete
            )
        )
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.deleted_count, 2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
