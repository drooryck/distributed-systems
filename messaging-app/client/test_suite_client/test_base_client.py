import sys
import os
import warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", message="Session state does not function when running a script without `streamlit run`")
import unittest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from client import ChatServerClient
import unittest
import json
import struct
import streamlit as st
from unittest.mock import patch, MagicMock

# Global settings for the tests
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555
USE_CUSTOM_PROTOCOL = True  # Set True for binary protocol, False for JSON

class BaseTestClient(unittest.TestCase):
    """Base test case class for client-side testing with a mock server connection."""

    def setUp(self):
        """Initialize a mock session state and client before each test."""

        st.session_state.clear()
        protocol_choice = "custom" if USE_CUSTOM_PROTOCOL else "json"
        self.client = ChatServerClient(SERVER_HOST, SERVER_PORT, protocol_choice)

    def mock_send_response(self, mock_socket, response_data, msg_type):
        """
        Helper function to simulate sending and receiving a response from the server.
        
        For the JSON protocol, the response is a 4-byte length prefix followed by
        a JSON-encoded message. For the custom protocol, the response is built using
        the custom binary format.
        """
        if USE_CUSTOM_PROTOCOL:
            # For the custom protocol, build the packet using the custom protocol handler.
            # The full packet is: [op_id:1][is_response:1] + payload.
            # The payload is generated by _encode_payload with is_response=True.
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
            from protocol.protocol import Message  # Ensure Message is imported
            
            op_id = self.client.protocol_handler.name_to_op.get(msg_type, 255)
            header = struct.pack("!B", op_id) + struct.pack("!B", 1)  # is_response=1
            payload = self.client.protocol_handler._encode_payload(msg_type, True, response_data)
            full_packet = header + payload
        else:
            # For the JSON protocol, the packet consists of a 4-byte length prefix
            # followed by the JSON-encoded message.
            response_json = json.dumps({"msg_type": msg_type, "data": response_data}).encode("utf-8")
            length_prefix = struct.pack("!I", len(response_json))
            full_packet = length_prefix + response_json

        # Simulate socket behavior by defining a recv() side_effect that returns
        # successive chunks from the full_packet.
        full_packet_buffer = full_packet

        def recv_side_effect(n):
            nonlocal full_packet_buffer
            ret = full_packet_buffer[:n]
            full_packet_buffer = full_packet_buffer[n:]
            return ret

        mock_socket.recv.side_effect = recv_side_effect