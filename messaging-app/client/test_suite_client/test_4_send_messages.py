from test_base_client import BaseTestClient
from unittest.mock import patch, MagicMock
import streamlit as st
import warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")
class TestSendMessage(BaseTestClient):
    @patch("socket.socket")
    def test_successful_message_send(self, mock_socket):
        """Test sending a message updates UI correctly."""
        mock_sock = MagicMock()
        self.mock_send_response(mock_sock, {"data": {"status": "ok"}})
        mock_socket.return_value = mock_sock

        st.session_state.username = "Alice"
        response = self.client.send_request("send_message", {
            "sender": "Alice",
            "recipient": "Bob",
            "content": "Hello!"
        })
        self.assertEqual(response["data"]["status"], "ok")

    @patch("socket.socket")
    def test_send_message_failure(self, mock_socket):
        """Test handling of message sending failure."""
        mock_sock = MagicMock()
        self.mock_send_response(mock_sock, {"data": {"status": "error", "msg": "Recipient not found"}})
        mock_socket.return_value = mock_sock

        response = self.client.send_request("send_message", {
            "sender": "Alice",
            "recipient": "Nonexistent",
            "content": "Hello!"
        })
        self.assertEqual(response["data"]["status"], "error")

if __name__ == "__main__":
    import unittest
    unittest.main()