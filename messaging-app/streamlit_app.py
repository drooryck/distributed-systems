#!/usr/bin/env python3
import streamlit as st
import socket
import json
import hashlib
import time
import struct  # Needed for packing/unpacking the 4-byte length prefix

# --- Custom CSS Styling ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    body {
        background-color: #f0f8ff;
        font-family: 'Roboto', sans-serif;
        color: #333333;
    }
    .reportview-container .main .block-container {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 2rem;
    }
    h1 {
        color: #1abc9c;
    }
    h2, h3, h4, h5, h6 {
        color: #34495e;
    }
    .sidebar .sidebar-content {
        background-color: #2c3e50;
        color: #ecf0f1;
    }
    .delete-btn {
        background: none;
        border: none;
        font-size: 1.5rem;
        cursor: pointer;
        color: #e74c3c;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------- Configuration ----------------
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

# ---------------- Helper Functions ----------------
def get_socket():
    """
    Get (or create) a persistent socket connection stored in Streamlit's session state.
    """
    if "socket" not in st.session_state:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((SERVER_HOST, SERVER_PORT))
            s.settimeout(5)
            st.session_state["socket"] = s
        except Exception as e:
            st.error(f"Failed to connect to server: {e}")
            return None
    return st.session_state["socket"]

def send_request(msg_type, data):
    """
    Send a request to the server using the same length-prefixed JSON protocol
    that JSON server expects.
    
    The message format is:
        {
            "msg_type": <action string>,   # e.g., "login", "signup", "send_message", etc.
            "data": { ... }                # a dict with the relevant fields
        }
    """
    s = get_socket()
    if not s:
        return None
    try:
        # Build the request message
        request = {"msg_type": msg_type, "data": data}
        encoded = json.dumps(request).encode("utf-8")
        # Prepend the 4-byte length prefix in network byte order
        length_prefix = struct.pack("!I", len(encoded))
        s.sendall(length_prefix + encoded)

        # Receive the 4-byte length of the response
        length_bytes = s.recv(4)
        if not length_bytes:
            st.error("No response from server. Connection closed.")
            return None
        (length,) = struct.unpack("!I", length_bytes)
        # Now receive the JSON response (assuming it fits in one recv)
        response_bytes = s.recv(length)
        if not response_bytes:
            st.error("No response from server after length prefix.")
            return None
        response = json.loads(response_bytes.decode("utf-8"))
        return response
    except Exception as e:
        st.error(f"Error communicating with server: {e}")
    return None

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# ---------------- Streamlit App Layout ----------------
# Initialize session state variables.
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "all_messages" not in st.session_state:
    st.session_state.all_messages = []  # Accumulated messages (delivered and new)
if "unread_count" not in st.session_state:
    st.session_state.unread_count = 0
if "username" not in st.session_state:
    st.session_state.username = ""
if "inbox_page" not in st.session_state:
    st.session_state.inbox_page = 0

st.title("Chat Application (JSON Protocol)")

# For simplicity, only features supported by the server are enabled.
if st.session_state.logged_in:
    st.sidebar.markdown(f"**Unread Messages: {st.session_state.unread_count}**")
    # Only the supported options are shown:
    menu = st.sidebar.radio("Navigation", ["Send Message", "Inbox", "Logout"])
else:
    menu = "Login / Signup"

# --- Login / Signup Section ---
if not st.session_state.logged_in:
    st.header("Login or Create Account")
    action = st.radio("Select Action", ["Login", "Create Account"])
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button(action):
        if not username or not password:
            st.error("Please enter both username and password.")
        else:
            hashed = hash_password(password)
            data = {"username": username, "password": hashed}
            if action == "Login":
                response = send_request("login", data)
                if response is None:
                    st.error("No response from server. Check that the server is running.")
                elif response.get("data", {}).get("status") == "ok":
                    st.success("Logged in successfully!")
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.unread_count = response.get("data", {}).get("unread_count", 0)
                    st.experimental_rerun()  # Force re-run so that main page is displayed
                else:
                    st.error(response.get("data", {}).get("msg", "Action failed."))
            else:  # "Create Account" option
                response = send_request("signup", data)
                if response is None:
                    st.error("No response from server. Check that the server is running.")
                elif response.get("data", {}).get("status") == "ok":
                    # Auto-login after successful account creation
                    login_response = send_request("login", data)
                    if login_response and login_response.get("data", {}).get("status") == "ok":
                        st.success("Account created and logged in successfully!")
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.unread_count = login_response.get("data", {}).get("unread_count", 0)
                        st.experimental_rerun()  # Immediately show the main page
                    else:
                        st.error(login_response.get("data", {}).get("msg", "Auto-login failed."))
                else:
                    st.error(response.get("data", {}).get("msg", "Action failed."))
else:
    # --- Main Page Views ---
    if menu == "Send Message":
        st.header("Send a Message")
        recipient = st.text_input("Recipient Username", key="recipient")
        message_text = st.text_area("Message", key="message_text")
        if st.button("Send"):
            if not recipient or not message_text:
                st.error("Please fill in all fields.")
            else:
                # The server expects keys: "sender", "recipient", and "content"
                data = {"sender": st.session_state.username,
                        "recipient": recipient,
                        "content": message_text}
                response = send_request("send_message", data)
                if response is None:
                    st.error("No response from server. Check that the server is running.")
                elif response.get("data", {}).get("status") == "ok":
                    st.success("Message sent!")
                else:
                    st.error(response.get("data", {}).get("msg", "Failed to send message."))
    elif menu == "Inbox":
        st.header("Inbox")
        if st.button("Fetch Messages"):
            # "num_messages" is the only parameter needed; the server will use the logged-in user.
            data = {"num_messages": 50}
            response = send_request("fetch_messages", data)
            if response and response.get("data", {}).get("status") == "ok":
                messages = response.get("data", {}).get("messages", [])
                # Avoid duplicating messages already in session state.
                existing_ids = {msg["id"] for msg in st.session_state.all_messages}
                for msg in messages:
                    if msg["id"] not in existing_ids:
                        st.session_state.all_messages.append(msg)
                st.session_state.unread_count = 0
                st.success(f"Fetched {len(messages)} message(s).")
            else:
                st.error(response.get("data", {}).get("msg", "Failed to fetch messages."))
        # Display fetched messages
        if st.session_state.all_messages:
            for msg in st.session_state.all_messages:
                with st.container():
                    st.markdown(f"**From:** {msg.get('sender')} &nbsp;&nbsp; **ID:** {msg.get('id')}")
                    st.markdown(f"<div style='padding: 0.5rem 0;'>{msg.get('content')}</div>", unsafe_allow_html=True)
                    if st.button("🗑️ Delete", key=f"delete_{msg['id']}"):
                        # The delete action expects a list of message IDs.
                        data = {"message_ids_to_delete": [msg["id"]]}
                        del_resp = send_request("delete_messages", data)
                        if del_resp and del_resp.get("data", {}).get("status") == "ok":
                            st.success(f"Deleted message ID {msg['id']}.")
                            st.session_state.all_messages = [m for m in st.session_state.all_messages if m["id"] != msg["id"]]
                            st.experimental_rerun()
                        else:
                            st.error(f"Failed to delete message ID {msg['id']}.")
                st.markdown("---")
        else:
            st.info("No messages to display.")
    elif menu == "Logout":
        if st.button("Logout"):
            response = send_request("logout", {})
            if response and response.get("data", {}).get("status") == "ok":
                st.success("Logged out.")
                st.session_state.logged_in = False
                st.session_state.username = ""
                # Close and remove the existing socket so that a new connection is created next time.
                if "socket" in st.session_state:
                    st.session_state["socket"].close()
                    del st.session_state["socket"]
                st.experimental_rerun()  # Rerun to show the login/signup page
            else:
                st.error(response.get("data", {}).get("msg", "Logout failed."))