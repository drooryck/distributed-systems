import socket
import json
import struct
import time

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555
LOG_FILE = "test_log.txt"

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

def test_message_reception():
    """Test message sending from Alice to Bob and Bob's message retrieval."""
    try:
        # Connect as Alice
        alice_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        alice_sock.connect((SERVER_HOST, SERVER_PORT))
        log("Alice connected to server.")

        # Sign up Alice
        send_message(alice_sock, "signup", {"username": "Alice", "password": "secret"})
        time.sleep(2)
        receive_response(alice_sock)

        # Sign up Bob
        send_message(alice_sock, "signup", {"username": "Bob", "password": "password"})
        time.sleep(2)
        receive_response(alice_sock)

        # Login Alice
        send_message(alice_sock, "login", {"username": "Alice", "password": "secret"})
        time.sleep(2)
        receive_response(alice_sock)

        # Alice sends a message to Bob
        send_message(alice_sock, "send_message", {"sender": "Alice", "recipient": "Bob", "content": "Hello, Bob!"})
        time.sleep(2)
        receive_response(alice_sock)

        # Close Alice's connection
        alice_sock.close()
        log("Alice disconnected.")

        # Wait to ensure message is stored
        time.sleep(4)

        # Connect as Bob
        bob_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bob_sock.connect((SERVER_HOST, SERVER_PORT))
        log("Bob connected to server.")

        # Bob logs in
        send_message(bob_sock, "login", {"username": "Bob", "password": "password"})
        time.sleep(2)
        receive_response(bob_sock)

        # Bob fetches messages
        send_message(bob_sock, "fetch_messages", {"num_messages": 5})
        time.sleep(2)
        response = receive_response(bob_sock)

        # Verify that Bob received at least one message
        assert response["data"]["status"] == "ok", "Fetch messages failed!"
        assert len(response["data"]["messages"]) > 0, "Bob did not receive any messages!"
        
        log("✅ Test Passed: Bob successfully received a message.")

        # Close Bob's connection
        bob_sock.close()
        log("Bob disconnected.")

    except AssertionError as e:
        log(f"❌ TEST FAILED: {e}")
    except Exception as e:
        log(f"Fatal error: {e}")

if __name__ == "__main__":
    test_message_reception()
