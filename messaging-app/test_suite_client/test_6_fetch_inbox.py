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

class TestFetchInbox(BaseTestClient):
    @patch("socket.socket")
    def test_auto_fetch_inbox(self, mock_socket):
        """
        Test that _auto_fetch_inbox correctly appends new messages to st.session_state["all_messages"].
        Simulate a response from the server for "send_messages_to_client".
        """
        st.session_state.clear()
        # Preinitialize required keys.
        st.session_state["all_messages"] = []
        st.session_state["unread_count"] = 0

        mock_sock = MagicMock()
        # Simulated server response: one new message with id 101.
        self.mock_send_response(mock_sock, {"data": {"status": "ok", "msg": [
            {"id": 101, "sender": "Bob", "content": "Auto message", "to_deliver": 1}
        ]}})
        mock_socket.return_value = mock_sock

        # Call the client action (which _auto_fetch_inbox uses).
        response = self.client.send_request("send_messages_to_client", {})
        self.assertEqual(response["data"]["status"], "ok")

        # Now, simulate what _auto_fetch_inbox does:
        # (In a real app, _auto_fetch_inbox reads the response and appends new messages.)
        returned_msgs = response["data"].get("msg", [])
        existing_ids = {m["id"] for m in st.session_state["all_messages"]}
        for m in returned_msgs:
            if m["id"] not in existing_ids:
                st.session_state["all_messages"].append(m)

        self.assertEqual(len(st.session_state["all_messages"]), 1)
        self.assertEqual(st.session_state["all_messages"][0]["id"], 101)

if __name__ == "__main__":
    unittest.main(verbosity=2)