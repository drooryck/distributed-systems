import socket
import struct
import unittest
import json
import sys
import os
import time

# Add the parent directory to sys.path to import 'protocol'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from protocol import JSONProtocolHandler, CustomProtocolHandler, Message

SERVER_HOST = "10.250.120.214"
SERVER_PORT = 5555
USE_CUSTOM_PROTOCOL = True  # Set True for binary protocol

class BaseTest(unittest.TestCase):
    """Base test class that resets the database before each test."""
    time = time

    def setUp(self):
        """Initialize socket, protocol, and reset the database before tests."""
        self.sock = socket.create_connection((SERVER_HOST, SERVER_PORT))
        self.protocol = CustomProtocolHandler() if USE_CUSTOM_PROTOCOL else JSONProtocolHandler()
        self.reset_database()

    def tearDown(self):
        """Close the socket after each test."""
        self.sock.close()

    def send_message(self, msg_type, data=None):
        """Send a structured message to the server."""
        message = Message(msg_type, data or {})
        self.protocol.send(self.sock, message)

    def receive_response(self):
        """Receive and parse a response from the server."""
        response = self.protocol.receive(self.sock)
        return response.data if response else None

    def reset_database(self):
        """Reset the database before each test using a temporary connection."""
        with socket.create_connection((SERVER_HOST, SERVER_PORT)) as temp_sock:
            self.protocol.send(temp_sock, Message("reset_db", {}))
            temp_sock.recv(1024)  # Clear response buffer
