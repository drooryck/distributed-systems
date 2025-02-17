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

class TestDeleteAccount(BaseTestClient):
    @patch("socket.socket")
    def test_delete_account_resets_session(self, mock_socket):
        """
        Test that a successful account deletion clears the session state,
        logging the user out.
        """
        st.session_state.clear()
        # Simulate a logged-in state.
        st.session_state["logged_in"] = True
        st.session_state["username"] = "Alice"
        st.session_state["unread_count"] = 5
        st.session_state["all_messages"] = [{"id": 101, "sender": "Alice", "content": "Hi"}]

        mock_sock = MagicMock()
        # Simulate a successful delete_account response.
        self.mock_send_response(
            mock_sock,
            {"status": "ok", "msg": "Account 'Alice' has been deleted. All associated messages are removed."},
            "delete_account"
        )
        mock_socket.return_value = mock_sock

        response = self.client.send_request("delete_account", {})
        print("###")
        print(response)
        print("###")
        self.assertEqual(response["status"], "ok")

        # In the UI, after a successful account deletion, session state is reset.
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["unread_count"] = 0
        st.session_state["all_messages"] = []

        self.assertFalse(st.session_state.get("logged_in", False))
        self.assertEqual(st.session_state.get("username", ""), "")
        self.assertEqual(st.session_state.get("unread_count", 0), 0)
        self.assertEqual(len(st.session_state.get("all_messages", [])), 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)