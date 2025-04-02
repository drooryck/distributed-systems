import struct
import json
import socket
import sys, os
# Add the parent directory to sys.path to import 'protocol'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from protocol import JSONProtocolHandler, CustomProtocolHandler, Message

# Flag to enable measurement mode
MEASURE_INFO = True  # You can toggle this in protocol.py

def measure_request_size(proto_handler, message):
    """Calculates the size of the encoded request."""
    if isinstance(proto_handler, JSONProtocolHandler):
        serialized_data = json.dumps({
            "msg_type": message["msg_type"],
            "data": message["data"]
        }).encode("utf-8")
        # 4 bytes for the length prefix
        return len(serialized_data) + 4
    else:
        serialized_data = proto_handler._encode_payload(
            message["msg_type"], 
            False, 
            message["data"]
        )
        # 2 bytes for [op_id, is_response]
        return len(serialized_data) + 2

def measure_bytes(proto_handler, message):
    """
    Sends a request using the given protocol handler, 
    then reads the server's response with a socket timeout to avoid blocking.
    Returns (request_size, response_size).
    """
    request_size = measure_request_size(proto_handler, message)
    response_size = 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)  # 3-second timeout to avoid blocking forever
    try:
        sock.connect(('127.0.0.1', 5000))  # Adjust port as needed

        # Send the request
        proto_handler.send(
            sock,
            Message(message["msg_type"], message["data"]),
            is_response=False
        )

        # Read the response
        if isinstance(proto_handler, JSONProtocolHandler):
            # For JSON, read the 4-byte prefix, then read the JSON body
            try:
                length_prefix = sock.recv(4)
                if length_prefix:
                    response_size += len(length_prefix)
                    (length,) = struct.unpack("!I", length_prefix)
                    if length > 0:
                        data = sock.recv(length)
                        if data:
                            response_size += len(data)
            except socket.timeout:
                # Timed out while waiting for the JSON response
                pass
        else:
            # For Custom protocol, just read everything until the server closes or we hit timeout
            try:
                while True:
                    chunk = sock.recv(1024)
                    if not chunk:
                        break
                    response_size += len(chunk)
            except socket.timeout:
                # Timed out while reading custom response
                pass
    except ConnectionRefusedError:
        print("Error: Could not connect to the server. Is it running on 127.0.0.1:5000?")
        return 0, 0
    finally:
        sock.close()

    return request_size, response_size

########################
# TEST FUNCTIONS
########################

def test_reset_db(proto_handler):
    message = {"msg_type": "reset_db", "data": {}}
    return measure_bytes(proto_handler, message)

def test_signup(proto_handler):
    test_reset_db(proto_handler)  # Clean slate
    message = {"msg_type": "signup", "data": {"username": "testuser", "password": "secure123"}}
    return measure_bytes(proto_handler, message)

def test_login(proto_handler):
    test_reset_db(proto_handler)
    test_signup(proto_handler)  # Ensure user exists
    message = {"msg_type": "login", "data": {"username": "testuser", "password": "secure123"}}
    return measure_bytes(proto_handler, message)

def test_logout(proto_handler):
    test_reset_db(proto_handler)
    test_signup(proto_handler)
    test_login(proto_handler)  # Logged in
    message = {"msg_type": "logout", "data": {}}
    return measure_bytes(proto_handler, message)

def test_send_message(proto_handler):
    test_reset_db(proto_handler)
    test_login(proto_handler)
    message = {
        "msg_type": "send_message",
        "data": {
            "sender": "testuser",
            "recipient": "friend",
            "content": "Hello!"
        }
    }
    return measure_bytes(proto_handler, message)

def test_count_unread(proto_handler):
    test_reset_db(proto_handler)
    test_signup(proto_handler)
    test_login(proto_handler)
    test_send_message(proto_handler)
    message = {"msg_type": "count_unread", "data": {}}
    return measure_bytes(proto_handler, message)

def test_send_messages_to_client(proto_handler):
    test_reset_db(proto_handler)
    test_signup(proto_handler)
    test_login(proto_handler)
    test_send_message(proto_handler)
    message = {
        "msg_type": "send_messages_to_client",
        "data": {}
    }
    return measure_bytes(proto_handler, message)

def test_fetch_away_msgs(proto_handler):
    test_reset_db(proto_handler)
    test_signup(proto_handler)
    test_login(proto_handler)
    message = {
        "msg_type": "fetch_away_msgs",
        "data": {
            "limit": 5
        }
    }
    return measure_bytes(proto_handler, message)

def test_list_accounts(proto_handler):
    test_reset_db(proto_handler)
    message = {
        "msg_type": "list_accounts",
        "data": {
            "count": 5,
            "start": 0,
            "pattern": "test"
        }
    }
    return measure_bytes(proto_handler, message)

def test_delete_messages(proto_handler):
    test_reset_db(proto_handler)
    test_signup(proto_handler)
    test_login(proto_handler)
    test_send_message(proto_handler)
    message = {
        "msg_type": "delete_messages",
        "data": {
            "message_ids_to_delete": [1]
        }
    }
    return measure_bytes(proto_handler, message)

def test_delete_account(proto_handler):
    test_reset_db(proto_handler)
    test_signup(proto_handler)
    test_login(proto_handler)
    message = {"msg_type": "delete_account", "data": {}}
    return measure_bytes(proto_handler, message)

########################
# MAIN
########################

def main():
    json_proto = JSONProtocolHandler()
    custom_proto = CustomProtocolHandler()
    
    tests = {
        "signup": test_signup,
        "login": test_login,
        "logout": test_logout,
        "count_unread": test_count_unread,
        "send_message": test_send_message,
        "send_messages_to_client": test_send_messages_to_client,
        "fetch_away_msgs": test_fetch_away_msgs,
        "list_accounts": test_list_accounts,
        "delete_messages": test_delete_messages,
        "delete_account": test_delete_account,
        "reset_db": test_reset_db
    }
    
    results = []
    
    for test_name, test_func in tests.items():
        # Run the test for JSON
        json_req_bytes, json_res_bytes = test_func(json_proto)
        # Run the test for Custom
        custom_req_bytes, custom_res_bytes = test_func(custom_proto)
        
        if json_req_bytes == 0:
            percentage = 0
        else:
            percentage = (custom_req_bytes / json_req_bytes) * 100
        
        results.append({
            "msg_type": test_name,
            "json_req_bytes": json_req_bytes,
            "json_res_bytes": json_res_bytes,
            "custom_req_bytes": custom_req_bytes,
            "custom_res_bytes": custom_res_bytes,
            "percentage": percentage
        })
    
    print("Message Type | JSON Req Bytes | JSON Res Bytes | Custom Req Bytes | Custom Res Bytes | Custom as % of JSON")
    print("-" * 90)
    for res in results:
        print(f"{res['msg_type']:12} | {res['json_req_bytes']:14} | {res['json_res_bytes']:14} "
              f"| {res['custom_req_bytes']:16} | {res['custom_res_bytes']:16} | {res['percentage']:6.2f}%")

if __name__ == "__main__":
    if MEASURE_INFO:
        main()
