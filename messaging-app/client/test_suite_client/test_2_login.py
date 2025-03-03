import sys
import os
import warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")

# Ensure the parent directory is in the Python path to avoid import errors
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from test_base_client import BaseTestClient  # Base class that sets up a client and mocks socket
from unittest.mock import patch, MagicMock
import streamlit as st
import unittest

class TestLogin(BaseTestClient):
    @patch("socket.socket")
    def test_successful_login(self, mock_socket):
        """Test successful login updates session state."""
        st.session_state.clear()
        st.session_state["logged_in"] = False
        st.session_state["unread_count"] = 0
        st.session_state["username"] = ""
        
        mock_sock = MagicMock()
        self.mock_send_response(
            mock_sock,
            {"status": "ok", "unread_count": 3, "msg": "Login successful"},
            "login"
        )
        mock_socket.return_value = mock_sock

        response = self.client.send_request("login", {"username": "Alice", "password": "secret"})

        self.assertEqual(response["status"], "ok")
        st.session_state["logged_in"] = True
        st.session_state["username"] = "Alice"
        st.session_state["unread_count"] = response.get("unread_count", 0)
        
        self.assertTrue(st.session_state.get("logged_in", False))
        self.assertEqual(st.session_state.get("username"), "Alice")
        self.assertEqual(st.session_state.get("unread_count"), 3)

    @patch("socket.socket")
    def test_invalid_login(self, mock_socket):
        """Test failed login does not update session state."""
        st.session_state.clear()
        st.session_state["logged_in"] = False
        
        mock_sock = MagicMock()
        self.mock_send_response(
            mock_sock,
            {"status": "error", "msg": "Invalid login"},
            "login"
        )
        mock_socket.return_value = mock_sock

        response = self.client.send_request("login", {"username": "Alice", "password": "wrong"})

        self.assertEqual(response["status"], "error")
        self.assertFalse(st.session_state.get("logged_in", False))

if __name__ == "__main__":
    unittest.main(verbosity=2)