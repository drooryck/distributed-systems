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

class TestListAccounts(BaseTestClient):
    @patch("socket.socket")
    def test_list_accounts_returns_expected_users(self, mock_socket):
        """
        Test that a list_accounts request with a pattern returns the expected list of users.
        """
        st.session_state.clear()
        mock_sock = MagicMock()
        # Simulate a server response: when pattern "a" is sent, return accounts for alice and charlie.
        self.mock_send_response(
            mock_sock,
            {"status": "ok", "users": [(1, "alice"), (2, "charlie")]},
            "list_accounts"
        )
        mock_socket.return_value = mock_sock

        response = self.client.send_request("list_accounts", {"pattern": "a", "start": 0, "count": 10})
        self.assertEqual(response["status"], "ok")
        # Extract usernames from the list of tuples.
        usernames = [uname for (_, uname) in response["users"]]
        self.assertIn("alice", usernames)
        self.assertIn("charlie", usernames)

if __name__ == "__main__":
    unittest.main(verbosity=2)