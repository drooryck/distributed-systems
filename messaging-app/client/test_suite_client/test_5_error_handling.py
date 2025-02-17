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

class TestErrorHandling(BaseTestClient):
    @patch("socket.socket")
    def test_network_failure(self, mock_socket):
        """
        Simulate a network failure by making socket.socket() raise an exception.
        The client.send_request should catch the exception and return None.
        """
        # Make socket.socket() raise an exception
        mock_socket.side_effect = Exception("Network failure")
        response = self.client.send_request("login", {"username": "Alice", "password": "secret"})
        self.assertIsNone(response)

    @patch("socket.socket")
    def test_socket_timeout(self, mock_socket):
        """
        Simulate a socket timeout by making recv() return an empty bytes object.
        The client.send_request should then report no response.
        """
        st.session_state.clear()
        mock_sock = MagicMock()
        # Simulate recv() returning empty bytes to mimic a timeout/closed connection.
        mock_sock.recv.return_value = b""
        mock_socket.return_value = mock_sock

        response = self.client.send_request("login", {"username": "Alice", "password": "secret"})
        self.assertIsNone(response)

    @patch("socket.socket")
    def test_server_disconnect(self, mock_socket):
        """
        Simulate a server disconnect (e.g. no response after sending request).
        """
        st.session_state.clear()
        mock_sock = MagicMock()
        # First recv() returns a proper length prefix, but the subsequent recv returns empty.
        length_prefix = b"\x00\x00\x00\x10"
        mock_sock.recv.side_effect = [length_prefix, b""]
        mock_socket.return_value = mock_sock

        response = self.client.send_request("login", {"username": "Alice", "password": "secret"})
        self.assertIsNone(response)

if __name__ == "__main__":
    unittest.main(verbosity=2)