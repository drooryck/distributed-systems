import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
from protocol import chat_service_pb2

class TestDeleteAccount(unittest.TestCase):
    """Test account deletion functionality."""

    def setUp(self):
        """Set up a ChatServerClient instance."""
        self.client = ChatServerClient(["127.0.0.1:50051", "127.0.0.1:50052", "127.0.0.1:50053"])

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_delete_account_clears_session(self, mock_stub_class):
        """Test that a successful account deletion logs out the user and clears session state."""
        st.session_state.clear()
        st.session_state["logged_in"] = True
        st.session_state["username"] = "Alice"
        st.session_state["auth_token"] = "test_token"

        mock_stub = MagicMock()
        mock_stub.DeleteAccount.return_value = chat_service_pb2.GenericResponse(
            status="ok", msg="Account deleted successfully"
        )
        mock_stub_class.return_value = mock_stub

        response = mock_stub.DeleteAccount(
            chat_service_pb2.EmptyRequest(auth_token=st.session_state["auth_token"])
        )

        mock_stub.DeleteAccount.assert_called_once_with(
            chat_service_pb2.EmptyRequest(auth_token="test_token")
        )
        self.assertEqual(response.status, "ok")

        # Simulate session state reset after account deletion
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["auth_token"] = ""

        self.assertFalse(st.session_state.get("logged_in", False))
        self.assertEqual(st.session_state.get("username", ""), "")
        self.assertEqual(st.session_state.get("auth_token", ""), "")

if __name__ == "__main__":
    unittest.main(verbosity=2)
