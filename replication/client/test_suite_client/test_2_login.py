import sys
import os
import warnings
import unittest
from unittest.mock import patch, MagicMock
import streamlit as st

# Ignore Streamlit warnings during testing
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
from protocol import chat_service_pb2

class TestLogin(unittest.TestCase):
    """Test login functionality with mocked gRPC server."""

    def setUp(self):
        """Setup a mock gRPC stub for testing."""
        self.client = ChatServerClient(["127.0.0.1:50051", "127.0.0.1:50052", "127.0.0.1:50053"])

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_successful_login(self, mock_stub_class):
        """Test successful login updates session state."""
        st.session_state.clear()

        mock_stub = MagicMock()
        mock_stub.Login.return_value = chat_service_pb2.LoginResponse(
            status="ok", auth_token="test_token", unread_count=3
        )
        mock_stub_class.return_value = mock_stub

        username = "Alice"
        password = "secret"
        hashed_pw = self.client.hash_password(password)

        response = mock_stub.Login(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))

        mock_stub.Login.assert_called_once_with(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))
        self.assertEqual(response.status, "ok")

        # Simulate session state update in Streamlit UI
        st.session_state["logged_in"] = True
        st.session_state["username"] = username
        st.session_state["unread_count"] = response.unread_count

        self.assertTrue(st.session_state["logged_in"])
        self.assertEqual(st.session_state["username"], "Alice")
        self.assertEqual(st.session_state["unread_count"], 3)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_invalid_login(self, mock_stub_class):
        """Test failed login does not update session state."""
        st.session_state.clear()

        mock_stub = MagicMock()
        mock_stub.Login.return_value = chat_service_pb2.LoginResponse(status="error", auth_token="", unread_count=0)
        mock_stub_class.return_value = mock_stub

        username = "Alice"
        password = "wrong"
        hashed_pw = self.client.hash_password(password)

        response = mock_stub.Login(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))

        mock_stub.Login.assert_called_once_with(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))
        self.assertEqual(response.status, "error")

        self.assertFalse(st.session_state.get("logged_in", False))

if __name__ == "__main__":
    unittest.main(verbosity=2)
