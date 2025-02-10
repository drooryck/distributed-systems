import socket
import json
import struct
import time

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555
LOG_FILE = "client_log.txt"

def log(msg):
    """Log messages to a file and print to console."""
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
    print(msg)

def send_message(sock, msg_type, data):
    """Send a structured message to the server."""
    try:
        payload = json.dumps({"msg_type": msg_type, "data": data}).encode("utf-8")
        sock.sendall(struct.pack("!I", len(payload)) + payload)
        log(f"Sent: {msg_type} -> {data}")
    except Exception as e:
        log(f"Error sending {msg_type}: {e}")

def receive_response(sock):
    """Receive and parse a response from the server."""
    try:
        length_prefix = sock.recv(4)
        if not length_prefix:
            log("Server closed connection.")
            return None
        
        length = struct.unpack("!I", length_prefix)[0]
        response = sock.recv(length).decode("utf-8")
        log(f"Received: {response}")
        return json.loads(response)
    except Exception as e:
        log(f"Error receiving response: {e}")
        return None

def run_tests():
    """Connect to the server and run basic tests."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_HOST, SERVER_PORT))
        log("Connected to server.")

        # Test 1: Signup
        send_message(sock, "signup", {"user": "Alice", "password": "secret"})
        receive_response(sock)
        time.sleep(2)
        # Test 2: Login
        send_message(sock, "login", {"user": "Alice", "password": "secret"})
        receive_response(sock)
        time.sleep(2)
        # Test 3: Send a message
        send_message(sock, "send_message", {"sender": "Alice", "recipient": "Bob", "content": "Hello, Bob!"})
        receive_response(sock)
        time.sleep(2)
        # Test 4: Send an unknown command
        send_message(sock, "unknown_command", {})
        receive_response(sock)
        time.sleep(2)
        sock.close()
        log("Disconnected from server.")
    except Exception as e:
        log(f"Fatal error: {e}")

if __name__ == "__main__":
    run_tests()
