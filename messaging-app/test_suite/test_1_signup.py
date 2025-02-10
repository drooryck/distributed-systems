import socket
import json
import struct

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

def test_signup():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))
    
    # Try signing up multiple accounts
    send_message(sock, "signup", {"username": "Charlie", "password": "abc123"})
    receive_response(sock)
    
    send_message(sock, "signup", {"username": "Dave", "password": "xyz789"})
    response = receive_response(sock)
    
    if response["data"]["status"] == "ok":
        print("✅ Test Passed: Multiple signups allowed from the same connection")
    else:
        print("❌ Test Failed: Multiple signups not allowed")

    sock.close()

if __name__ == "__main__":
    test_signup()
