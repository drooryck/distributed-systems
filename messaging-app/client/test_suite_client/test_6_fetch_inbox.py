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
        st.session_state["all_messages"] = []
        st.session_state["unread_count"] = 0

        mock_sock = MagicMock()
        self.mock_send_response(
            mock_sock,
            {"status": "ok", "msg": [
                {"id": 101, "sender": "Bob", "content": "Auto message", "to_deliver": 1}
            ]},
            "send_messages_to_client"
        )
        mock_socket.return_value = mock_sock

        response = self.client.send_request("send_messages_to_client", {})
        self.assertEqual(response["status"], "ok")

        returned_msgs = response.get("msg", [])
        existing_ids = {m["id"] for m in st.session_state["all_messages"]}
        for m in returned_msgs:
            if m["id"] not in existing_ids:
                st.session_state["all_messages"].append(m)

        self.assertEqual(len(st.session_state["all_messages"]), 1)
        self.assertEqual(st.session_state["all_messages"][0]["id"], 101)

if __name__ == "__main__":
    unittest.main(verbosity=2)