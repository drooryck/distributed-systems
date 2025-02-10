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

def test_pending_messages():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))
    
    send_message(sock, "signup", {"username": "Alice", "password": "secret"})
    receive_response(sock)

    send_message(sock, "signup", {"username": "Bob", "password": "password"})
    receive_response(sock)

    send_message(sock, "login", {"username": "Bob", "password": "password"})
    receive_response(sock)

    send_message(sock, "send_message", {"sender": "Bob", "recipient": "Alice", "content": "Hey Alice!"})
    receive_response(sock)

    send_message(sock, "send_message", {"sender": "Bob", "recipient": "Alice", "content": "Message 2!"})
    receive_response(sock)

    # Close Bob's connection
    sock.close()

    # Connect as Alice
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))

    send_message(sock, "login", {"username": "Alice", "password": "secret"})
    response = receive_response(sock)

    #print(response)

    unread_count = response["data"]["unread_count"]
    assert unread_count == 2, "❌ Test Failed: Alice should have received 2 messages!"
    print("✅ Test Passed: Alice received pending messages.")


    sock.close()

if __name__ == "__main__":
    test_pending_messages()
