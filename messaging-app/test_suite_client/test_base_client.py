import sys
import os
import warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient

import unittest
import json
import struct
import streamlit as st
from unittest.mock import patch, MagicMock
from client import ChatServerClient

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

class BaseTestClient(unittest.TestCase):
    """Base test case class for client-side testing with a mock server connection."""

    def setUp(self):
        """Initialize a mock session state and client before each test."""
        st.session_state.clear()
        self.client = ChatServerClient(SERVER_HOST, SERVER_PORT)

    def mock_send_response(self, mock_socket, response_data):
        """Helper function to simulate sending and receiving a response."""
        response_json = json.dumps(response_data).encode("utf-8")
        length_prefix = struct.pack("!I", len(response_json))
        mock_socket.recv.side_effect = [length_prefix, response_json]