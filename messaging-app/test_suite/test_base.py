import socket
import json
import struct
import unittest

SERVER_HOST = "10.250.120.214"
SERVER_PORT = 5555


class BaseTest(unittest.TestCase):
    """Base test case class that resets the database before each test."""

    def setUp(self):
        """Reset the database before each test runs."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER_HOST, SERVER_PORT))

    def tearDown(self):
        """Close the socket after each test."""
        self.sock.close()

    def send_message(self, msg_type, data):
        """Send a structured message to the server."""
        if data is None:
            data = {}  # Ensure we always send a valid JSON object

        payload = json.dumps({"msg_type": msg_type, "data": data}).encode("utf-8")
        self.sock.sendall(struct.pack("!I", len(payload)) + payload)

    def receive_response(self):
        """Receive and parse a response from the server."""
        length_prefix = self.sock.recv(4)
        if not length_prefix:
            print("Server closed connection.")
            return None
        length = struct.unpack("!I", length_prefix)[0]
        response = self.sock.recv(length).decode("utf-8")
        print(f"Received: {response}")
        return json.loads(response)

    def reset_database(self):
        """Send a request to reset the database before tests."""
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_sock.connect((SERVER_HOST, SERVER_PORT))

        payload = json.dumps({"msg_type": "reset_db", "data": {}}).encode("utf-8")
        temp_sock.sendall(struct.pack("!I", len(payload)) + payload)

        length_prefix = temp_sock.recv(4)
        if length_prefix:
            length = struct.unpack("!I", length_prefix)[0]
            response = temp_sock.recv(length).decode("utf-8")
            print("⚠️ Database Reset Response:", response)
        
        temp_sock.close()

