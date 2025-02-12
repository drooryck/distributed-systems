import struct
import json

class Message:
    """ Represents a generic message with a type and data payload. """
    def __init__(self, msg_type, data):
        self.msg_type = msg_type
        self.data = data

    def __repr__(self):
        return f"<Message type={self.msg_type}, data={self.data}>"

class JSONProtocolHandler:
    """ Handles sending and receiving JSON-based messages with length-prefixing. """
    def send(self, conn, message: Message):
        payload = {
            "msg_type": message.msg_type,
            "data": message.data
        }
        encoded = json.dumps(payload).encode("utf-8")
        conn.sendall(struct.pack("!I", len(encoded)))
        conn.sendall(encoded)

    def receive(self, conn):
        length_prefix = conn.recv(4)
        if not length_prefix:
            return None
        (length,) = struct.unpack("!I", length_prefix)
        if length == 0:
            return None
        data = conn.recv(length)
        if not data:
            return None
        payload = json.loads(data.decode("utf-8"))
        return Message(payload["msg_type"], payload["data"])

class TrueBinaryProtocolHandler:
    """ Handles sending and receiving messages using a true binary protocol. """
    def send(self, conn, message: Message):
        msg_type_encoded = message.msg_type.encode("utf-8")
        msg_type_len = len(msg_type_encoded)

        # Assume data contains a dictionary with two integer values
        data_values = list(message.data.values())  # Example: {"value1": 42, "value2": 99}
        packed_data = struct.pack("!II", *data_values)  # Two integers (4 bytes each)

        combined = struct.pack("!I", msg_type_len) + msg_type_encoded + packed_data
        conn.sendall(struct.pack("!I", len(combined)))  # Send total message length
        conn.sendall(combined)

    def receive(self, conn):
        length_prefix = conn.recv(4)
        if not length_prefix:
            return None
        (length,) = struct.unpack("!I", length_prefix)
        if length == 0:
            return None

        data = conn.recv(length)
        if not data:
            return None

        # Extract message type
        msg_type_len = struct.unpack("!I", data[:4])[0]
        msg_type = data[4:4 + msg_type_len].decode("utf-8")

        # Extract integer values
        data_values = struct.unpack("!II", data[4 + msg_type_len:])  # Assuming 2 integers
        return Message(msg_type, {"value1": data_values[0], "value2": data_values[1]})

class CustomProtocolHandler:
    """
    Handles sending and receiving messages with a custom (binary) wire protocol.
    This is just a minimal placeholder.
    """
    
    """
    def send(self, conn, message: Message):
        msg_type_encoded = message.msg_type.encode("utf-8")
        msg_type_len = len(msg_type_encoded)
        
        # Assume data contains a simple dictionary with integer fields
        data_values = list(message.data.values())  # Example: {"value1": 42, "value2": 99}
        packed_data = struct.pack("!II", *data_values)  # 2 Integers (4 bytes each)

        combined = struct.pack("!I", msg_type_len) + msg_type_encoded + packed_data
        conn.sendall(struct.pack("!I", len(combined)))  # Send total message length
        conn.sendall(combined)

    def receive(self, conn):
        length_prefix = conn.recv(4)
        if not length_prefix:
            return None
        (length,) = struct.unpack("!I", length_prefix)
        if length == 0:
            return None

        data = conn.recv(length)
        if not data:
            return None

        # Extract message type
        msg_type_len = struct.unpack("!I", data[:4])[0]
        msg_type = data[4:4 + msg_type_len].decode("utf-8")

        # Extract integer values
        data_values = struct.unpack("!II", data[4 + msg_type_len:])  # Assuming 2 integers
        return Message(msg_type, {"value1": data_values[0], "value2": data_values[1]})
        """
    
    def send(self, conn, message: Message):
        msg_type_encoded = message.msg_type.encode("utf-8")
        data_json = json.dumps(message.data).encode("utf-8")
        combined = msg_type_encoded + b"\x00" + data_json
        conn.sendall(struct.pack("!I", len(combined)))
        conn.sendall(combined)

    def receive(self, conn):
        length_prefix = conn.recv(4)
        if not length_prefix:
            return None
        (length,) = struct.unpack("!I", length_prefix)
        if length == 0:
            return None

        # Read exactly 'length' bytes
        data = b""
        while len(data) < length:
            chunk = conn.recv(length - len(data))
            if not chunk:
                return None
            data += chunk

        parts = data.split(b"\x00", 1)
        if len(parts) < 2:
            return None
        msg_type_encoded, json_data = parts
        msg_type = msg_type_encoded.decode("utf-8")
        data_dict = json.loads(json_data.decode("utf-8"))

        return Message(msg_type, data_dict)
