import socket
import json
import struct
import time

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

def send_message(sock, msg_type, data):
    payload = json.dumps({"msg_type": msg_type, "data": data}).encode("utf-8")
    sock.sendall(struct.pack("!I", len(payload)) + payload)

def receive_response(sock):
    length_prefix = sock.recv(4)
    if not length_prefix:
        print("Server closed connection.")
        return None
    length = struct.unpack("!I", length_prefix)[0]
    response = sock.recv(length).decode("utf-8")
    print(f"Received: {response}")
    return json.loads(response)

def test_login():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))
    
    # Signup for Alice (if not already signed up)
    send_message(sock, "signup", {"username": "Alice", "password": "secret"})
    receive_response(sock)
    
    # Alice logs in
    send_message(sock, "login", {"username": "Alice", "password": "secret"})
    response = receive_response(sock)
    
    # Try logging in again with another account (Bob) on the same connection
    send_message(sock, "login", {"username": "Bob", "password": "password"})
    response = receive_response(sock)
    
    if response["data"]["status"] == "error":
        print("✅ Test Passed: Cannot log into two accounts from the same connection")
    else:
        print("❌ Test Failed: Allowed logging into multiple accounts")

    sock.close()

if __name__ == "__main__":
    test_login()
