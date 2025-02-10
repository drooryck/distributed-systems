# This test ensures: 1️⃣ Logging in with the wrong password should fail.
# 2️⃣ Logging in without a username or password should fail.
# 3️⃣ Logging in with an unregistered username should fail.

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

def test_invalid_login():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))

    ### 1️⃣ Sign up a valid user ###
    send_message(sock, "signup", {"username": "Alice", "password": "correct_password"})
    receive_response(sock)

    ### 2️⃣ Attempt login with wrong password ###
    send_message(sock, "login", {"username": "Alice", "password": "wrong_password"})
    response = receive_response(sock)
    assert response["data"]["status"] == "error", "❌ Test Failed: Logged in with wrong password!"
    print("✅ Test Passed: Cannot log in with the wrong password.")

    ### 3️⃣ Attempt login with missing password ###
    send_message(sock, "login", {"username": "Alice"})
    response = receive_response(sock)
    assert response["data"]["status"] == "error", "❌ Test Failed: Logged in without a password!"
    print("✅ Test Passed: Cannot log in without a password.")

    ### 4️⃣ Attempt login with missing username ###
    send_message(sock, "login", {"password": "correct_password"})
    response = receive_response(sock)
    assert response["data"]["status"] == "error", "❌ Test Failed: Logged in without a username!"
    print("✅ Test Passed: Cannot log in without a username.")

    ### 5️⃣ Attempt login with an unregistered username ###
    send_message(sock, "login", {"username": "GhostUser", "password": "password123"})
    response = receive_response(sock)
    assert response["data"]["status"] == "error", "❌ Test Failed: Logged in with a non-existent user!"
    print("✅ Test Passed: Cannot log in with an unregistered user.")

    sock.close()

if __name__ == "__main__":
    test_invalid_login()
