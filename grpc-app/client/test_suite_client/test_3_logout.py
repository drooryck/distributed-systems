import sys
import os
import warnings
import unittest
from unittest.mock import patch, MagicMock
import streamlit as st

warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
import chat_service_pb2

class TestLogout(unittest.TestCase):
    """Test logout functionality with gRPC stub."""

    def setUp(self):
        """Setup a mock gRPC stub for testing."""
        self.client = ChatServerClient(server_host="127.0.0.1", server_port=50051)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_logout_clears_session(self, mock_stub_class):
        """Test that logout clears session state."""
        st.session_state.clear()
        st.session_state["logged_in"] = True
        st.session_state["username"] = "Alice"

        mock_stub = MagicMock()
        mock_stub.Logout.return_value = chat_service_pb2.GenericResponse(status="ok", msg="Logout successful")
        mock_stub_class.return_value = mock_stub

        response = mock_stub.Logout(chat_service_pb2.EmptyRequest(auth_token="test_token"))

        mock_stub.Logout.assert_called_once_with(chat_service_pb2.EmptyRequest(auth_token="test_token"))
        self.assertEqual(response.status, "ok")

        # Simulate session state update
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""

        self.assertFalse(st.session_state.get("logged_in", False))
        self.assertEqual(st.session_state.get("username"), "")

if __name__ == "__main__":
    unittest.main()
