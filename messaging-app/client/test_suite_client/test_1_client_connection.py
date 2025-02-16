import sys
import os
import warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")

# Ensure the parent directory is in the Python path to avoid import errors
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../client.py")))

from test_base_client import BaseTestClient  # Correct relative import
from unittest.mock import patch, MagicMock
import socket

class TestClientConnection(BaseTestClient):
    @patch("socket.socket")
    def test_successful_connection(self, mock_socket):
        """Test if the client successfully establishes a socket connection."""
        mock_sock_instance = MagicMock()
        mock_socket.return_value = mock_sock_instance

        conn = self.client._get_socket()
        self.assertEqual(conn, mock_sock_instance)
    
    @patch("socket.socket")
    def test_connection_failure(self, mock_socket):
        """Test handling of connection failure."""
        mock_socket.side_effect = socket.error("Connection failed")
        conn = self.client._get_socket()
        self.assertIsNone(conn)

if __name__ == "__main__":
    import unittest
    unittest.main()