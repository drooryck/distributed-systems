# This test ensures: 1️⃣ fetch_messages should fail if no user is logged in.
# 2️⃣ send_message should fail if no user is logged in.
# 3️⃣ A logged-in user can only send messages as themselves.

import socket
import json
import struct

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

def send_message(sock, msg_type, data):
    """Send a structured message to the server."""
    payload = json.dumps({"msg_type": msg_type, "data": data}).encode("utf-8")
    sock.sendall(struct.pack("!I", len(payload)) + payload)

def receive_response(sock):
    """Receive and parse a response from the server."""
    length_prefix = sock.recv(4)
    if not length_prefix:
        print("Server closed connection.")
        return None
    length = struct.unpack("!I", length_prefix)[0]
    response = sock.recv(length).decode("utf-8")
    print(f"Received: {response}")
    return json.loads(response)

def test_authentication_required():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))

    ### 1️⃣ `fetch_messages` should fail if no user is logged in ###
    send_message(sock, "fetch_messages", {"num_messages": 5})
    response = receive_response(sock)
    assert response["data"]["status"] == "error", "❌ Test Failed: Fetching messages without login should not be allowed!"
    print("✅ Test Passed: `fetch_messages` is blocked without login.")

    ### 2️⃣ `send_message` should fail if no user is logged in ###
    send_message(sock, "send_message", {"sender": "Alice", "recipient": "Bob", "content": "Hello Bob!"})
    response = receive_response(sock)
    assert response["data"]["status"] == "error", "❌ Test Failed: Sending messages without login should not be allowed!"
    print("✅ Test Passed: `send_message` is blocked without login.")

    ### 3️⃣ A logged-in user can only send messages as themselves ###
    send_message(sock, "signup", {"username": "Alice", "password": "secret"})
    receive_response(sock)

    send_message(sock, "signup", {"username": "Bob", "password": "password"})
    receive_response(sock)

    send_message(sock, "login", {"username": "Alice", "password": "secret"})
    receive_response(sock)

    send_message(sock, "send_message", {"sender": "Bob", "recipient": "Charlie", "content": "Message from Alice as Bob!"})
    response = receive_response(sock)
    assert response["data"]["status"] == "error", "❌ Test Failed: Alice should not be able to send messages as Bob!"
    print("✅ Test Passed: Users cannot send messages as other users.")

    sock.close()

if __name__ == "__main__":
    test_authentication_required()
