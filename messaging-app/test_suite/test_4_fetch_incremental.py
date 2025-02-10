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

def test_message_delivery_status():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))

    # 1️⃣ Signup users
    send_message(sock, "signup", {"username": "Frank", "password": "pass123"})
    receive_response(sock)

    send_message(sock, "signup", {"username": "Alice", "password": "secret"})
    receive_response(sock)

    # 2️⃣ Alice logs in and sends a message to Frank
    send_message(sock, "login", {"username": "Alice", "password": "secret"})
    receive_response(sock)

    send_message(sock, "send_message", {"sender": "Alice", "recipient": "Frank", "content": "Hello Frank!"})
    receive_response(sock)

    # 3️⃣ Alice logs out
    sock.close()

    # 4️⃣ Frank logs in and fetches messages for the first time
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))

    send_message(sock, "login", {"username": "Frank", "password": "pass123"})
    receive_response(sock)

    send_message(sock, "fetch_messages", {"num_messages": 5})
    first_fetch = receive_response(sock)

    print("First fetch messages:", first_fetch["data"]["messages"])

    assert len(first_fetch["data"]["messages"]) == 1, "❌ Test Failed: Frank should have received 1 message."
    print("✅ Test Passed: Frank fetched 1 message.")

    # 5️⃣ Fetch messages again (should return nothing)
    send_message(sock, "fetch_messages", {"num_messages": 5})
    second_fetch = receive_response(sock)

    print("Second fetch messages:", second_fetch["data"]["messages"])

    assert len(second_fetch["data"]["messages"]) == 0, "❌ Test Failed: Already fetched messages should not reappear."
    print("✅ Test Passed: Previously fetched messages are marked as delivered.")

    sock.close()

if __name__ == "__main__":
    test_message_delivery_status()
