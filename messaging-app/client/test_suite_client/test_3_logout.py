import sys
import os
import warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")

# Ensure the parent directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from test_base_client import BaseTestClient  # Base test class that sets up self.client, etc.
from unittest.mock import patch, MagicMock
import streamlit as st
import unittest

class TestLogout(BaseTestClient):
    @patch("socket.socket")
    def test_logout_clears_session(self, mock_socket):
        """Test that logout clears session state."""
        st.session_state.clear()
        st.session_state["logged_in"] = True
        
        mock_sock = MagicMock()
        self.mock_send_response(
            mock_sock,
            {"status": "ok", "msg": "Logout successful"},
            "logout"
        )
        mock_socket.return_value = mock_sock

        response = self.client.send_request("logout", {})
        self.assertEqual(response["status"], "ok")

        st.session_state["logged_in"] = False
        self.assertFalse(st.session_state.get("logged_in", False))

if __name__ == "__main__":
    unittest.main()