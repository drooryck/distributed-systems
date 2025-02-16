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

class TestOfflineMessageFetch(BaseTestClient):
    @patch("socket.socket")
    def test_manual_fetch_offline_messages(self, mock_socket):
        """
        Test that manual fetching of offline messages (action "fetch_away_msgs")
        correctly adds messages to st.session_state["all_messages"].
        """
        st.session_state.clear()
        st.session_state["all_messages"] = []

        mock_sock = MagicMock()
        # Simulate offline message response: one message with id 202.
        self.mock_send_response(mock_sock, {"data": {"status": "ok", "msg": [
            {"id": 202, "sender": "Alice", "content": "Offline message", "to_deliver": 0}
        ]}})
        mock_socket.return_value = mock_sock

        response = self.client.send_request("fetch_away_msgs", {"limit": 5})
        self.assertEqual(response["data"]["status"], "ok")

        for m in response["data"]["msg"]:
            st.session_state["all_messages"].append(m)

        self.assertEqual(len(st.session_state["all_messages"]), 1)
        self.assertEqual(st.session_state["all_messages"][0]["id"], 202)

if __name__ == "__main__":
    unittest.main(verbosity=2)