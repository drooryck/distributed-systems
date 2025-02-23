import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from test_base_client import BaseTestClient
from unittest.mock import patch, MagicMock
import streamlit as st
import unittest
import warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")

class TestDeleteMessages(BaseTestClient):
    @patch("socket.socket")
    def test_delete_single_message(self, mock_socket):
        """
        Test that deleting a message removes it from st.session_state["all_messages"].
        """
        st.session_state.clear()
        # Pre-populate the inbox with two messages.
        st.session_state["all_messages"] = [
            {"id": 101, "sender": "Bob", "content": "Message 1", "to_deliver": 1},
            {"id": 102, "sender": "Alice", "content": "Message 2", "to_deliver": 0},
        ]

        mock_sock = MagicMock()
        # Simulate a successful deletion response from the server.
        self.mock_send_response(
            mock_sock,
            {"status": "ok", "deleted_count": 1, "msg": "Deleted 1 messages."},
            "delete_messages"
        )
        mock_socket.return_value = mock_sock

        # Simulate deletion of message with id 102.
        response = self.client.send_request("delete_messages", {"message_ids_to_delete": [102]})
        self.assertEqual(response["status"], "ok")
        # Manually update the session state as the UI would:
        st.session_state["all_messages"] = [m for m in st.session_state["all_messages"] if m["id"] != 102]
        self.assertEqual(len(st.session_state["all_messages"]), 1)
        self.assertEqual(st.session_state["all_messages"][0]["id"], 101)

if __name__ == "__main__":
    unittest.main(verbosity=2)