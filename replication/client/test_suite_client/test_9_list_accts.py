import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
import chat_service_pb2

class TestListAccounts(unittest.TestCase):
    """Test listing of user accounts."""

    def setUp(self):
        """Set up a ChatServerClient instance."""
        self.client = ChatServerClient(server_host="127.0.0.1", server_port=50051)

    @patch("client.chat_service_pb2_grpc.ChatServiceStub")
    def test_list_accounts_returns_expected_users(self, mock_stub_class):
        """Test that listing accounts returns the expected user list."""
        st.session_state.clear()

        mock_stub = MagicMock()
        mock_stub.ListAccounts.return_value = chat_service_pb2.ListAccountsResponse(
            status="ok",
            users=[
                chat_service_pb2.UserRecord(id=1, username="alice"),
                chat_service_pb2.UserRecord(id=2, username="charlie"),
            ],
        )
        mock_stub_class.return_value = mock_stub

        response = mock_stub.ListAccounts(
            chat_service_pb2.ListAccountsRequest(auth_token="test_token", pattern="a", start=0, count=10)
        )

        mock_stub.ListAccounts.assert_called_once_with(
            chat_service_pb2.ListAccountsRequest(auth_token="test_token", pattern="a", start=0, count=10)
        )
        self.assertEqual(response.status, "ok")

        usernames = [user.username for user in response.users]
        self.assertIn("alice", usernames)
        self.assertIn("charlie", usernames)

if __name__ == "__main__":
    unittest.main(verbosity=2)
