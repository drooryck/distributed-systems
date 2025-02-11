#!/usr/bin/env python3
import streamlit as st
import socket
import json
import hashlib
import struct  # Needed for packing/unpacking the 4-byte length prefix
import time

# pip install streamlit-autorefresh
from streamlit_autorefresh import st_autorefresh


class ChatServerClient:
    """
    Encapsulates server connection behavior and JSON communication protocol
    (length-prefixed JSON messages).
    """

    def __init__(self, server_host="127.0.0.1", server_port=5555):
        self.server_host = server_host
        self.server_port = server_port
    
    def _get_socket(self):
        """
        Get (or create) a persistent socket connection stored in Streamlit's session state.
        """
        if "socket" not in st.session_state:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((self.server_host, self.server_port))
                s.settimeout(5)
                st.session_state["socket"] = s
            except Exception as e:
                st.error(f"Failed to connect to server: {e}")
                return None
        return st.session_state["socket"]

    def send_request(self, msg_type, data):
        """
        Send a request to the server using length-prefixed JSON.
        The message format is:
            {
                "msg_type": <action string>,   # e.g., "login", "signup"
                "data": { ... }               # a dict with the relevant fields
            }
        """
        s = self._get_socket()
        if not s:
            return None
        try:
            request = {"msg_type": msg_type, "data": data}
            encoded = json.dumps(request).encode("utf-8")
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

            return json.loads(response_bytes.decode("utf-8"))
        except Exception as e:
            st.error(f"Error communicating with server: {e}")
        return None

    @staticmethod
    def hash_password(password):
        """
        Return a SHA-256 hash of the password for secure transmission.
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()


class StreamlitChatApp:
    """
    Main application class for our Streamlit-based Chat App.
    Handles layout, user actions, and state management around ChatServerClient.

    Changes for "while-logged-in" vs. "while-away" messages:
      - We call `send_all_messages_to_client` automatically while the user is logged in,
        to receive any newly-sent messages that arrived in real-time (sent_while_away=0)
        and also retrieve previously-delivered messages if the server so chooses.
      - We call `fetch_messages` manually to retrieve messages that arrived
        while the user was away/offline (sent_while_away=1), letting the user specify
        how many messages to fetch at once.
    """

    def __init__(self, server_host="127.0.0.1", server_port=5555):
        self.server_host = server_host
        self.server_port = server_port
        self.client = ChatServerClient(server_host, server_port)
        self._initialize_session_state()

    def _initialize_session_state(self):
        """
        Initialize any session_state variables if they do not exist yet.
        """
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False
        if "all_messages" not in st.session_state:
            st.session_state.all_messages = []  # Accumulated messages (delivered + newly fetched)
        if "unread_count" not in st.session_state:
            st.session_state.unread_count = 0
        if "username" not in st.session_state:
            st.session_state.username = ""
        if "inbox_page" not in st.session_state:
            st.session_state.inbox_page = 0
        # We'll store the user's desired manual fetch count in session state.
        if "manual_fetch_count" not in st.session_state:
            st.session_state.manual_fetch_count = 50  # Default to 50 for manual retrieval

    def apply_custom_css(self):
        """
        Injects custom CSS into the Streamlit app for improved styling.
        """
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
            """,
            unsafe_allow_html=True
        )

    def show_login_or_signup_page(self):
        """
        Displays the login / signup UI. If a user logs in or creates an account,
        updates session state accordingly.
        """
        st.header("Login or Create Account")
        action = st.radio("Select Action", ["Login", "Create Account"])
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button(action):
            if not username or not password:
                st.error("Please enter both username and password.")
                return

            hashed_pw = self.client.hash_password(password)
            data = {"username": username, "password": hashed_pw}

            if action == "Login":
                response = self.client.send_request("login", data)
                if response is None:
                    st.error("No response from server. Check that the server is running.")
                    return

                if response.get("data", {}).get("status") == "ok":
                    st.success("Logged in successfully!")
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.unread_count = response.get("data", {}).get("unread_count", 0)
                    st.experimental_rerun()
                else:
                    st.error(response.get("data", {}).get("msg", "Action failed."))

            else:  # Create Account
                response = self.client.send_request("signup", data)
                if response is None:
                    st.error("No response from server. Check that the server is running.")
                    return

                if not response.get("data", {}).get("status") == "ok":
                    st.error(response.get("data", {}).get("msg", "Action failed."))
                    return

                # Auto-login after successful account creation
                login_response = self.client.send_request("login", data)
                # Check if auto-login was actually successful
                if not login_response or login_response.get("data", {}).get("status") != "ok":
                    st.error("Account created but auto-login failed.")
                    return

                st.success("Account created and logged in successfully!")
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.unread_count = login_response.get("data", {}).get("unread_count", 0)
                st.experimental_rerun()

    def show_home_page(self):
        """
        Displays a simple home/landing page upon successful login.
        """
        st.header("Welcome!")
        st.write(f"You have {st.session_state.unread_count} unread message(s).")
        st.info("Use the sidebar to navigate to Send Message, Inbox, or Logout.")

    def show_send_message_page(self):
        """
        Page to send a new message to another user.
        (If the user is logged in, the server will consider sent_while_away=0 for these messages.)
        """
        st.header("Send a Message")
        recipient = st.text_input("Recipient Username", key="recipient")
        message_text = st.text_area("Message", key="message_text")

        if st.button("Send"):
            if not recipient or not message_text:
                st.error("Please fill in all fields.")
                return

            data = {
                "sender": st.session_state.username,
                "recipient": recipient,
                "content": message_text
            }
            response = self.client.send_request("send_message", data)
            if response is None:
                st.error("No response from server. Check that the server is running.")
            elif not response.get("data", {}).get("status") == "ok":
                st.error(response.get("data", {}).get("msg", "Failed to send message."))
            else:
                st.success("Message sent!")

    def _auto_fetch_logged_in_messages(self):
        """
        Helper method to auto-fetch messages that arrived while the user is logged in.
        This calls the new 'send_all_messages_to_client' action.

        The server will:
          - Deliver any new messages with sent_while_away=0, marking them delivered=1
          - Potentially include previously-delivered messages if it chooses (the server logic decides).
        """
        resp = self.client.send_request("send_all_messages_to_client", {})
        if resp and resp.get("data", {}).get("status") == "ok":
            # The server returns a list of messages in resp["data"]["messages"], presumably
            new_msgs = resp.get("data", {}).get("messages", [])
            existing_ids = {m["id"] for m in st.session_state.all_messages}
            added_count = 0
            for m in new_msgs:
                if m["id"] not in existing_ids:
                    st.session_state.all_messages.append(m)
                    added_count += 1
            # The server might also update unread counts, or we can set them ourselves:
            st.session_state.unread_count = 0  # We reset it, but you may refine the logic
            if added_count > 0:
                st.info(f"Auto-fetched {added_count} new message(s).")

    def show_inbox_page(self):
        """
        Displays messages in the user's inbox. We do two fetches:
          1) Automatic fetch (every 5s) for messages that arrived while user is logged in.
             This calls 'send_all_messages_to_client' behind the scenes.
          2) A manual button for retrieving messages that were sent while the user was away/offline.
             This calls 'fetch_messages' with a user-specified number to retrieve.
        """
        st.header("Inbox")

        # Insert an autorefresh to re-run every 5 seconds to fetch new messages automatically.
        st_autorefresh(interval=5000, key="inbox_autorefresh")

        # Perform auto-fetch for "while-logged-in" messages
        self._auto_fetch_logged_in_messages()

        # Manual fetch for a specific number of "offline/away" messages (sent_while_away=1).
        st.write("**Manually fetch offline (away) messages**")
        st.session_state.manual_fetch_count = st.number_input(
            "How many 'away' messages to fetch at once?",
            min_value=1,
            max_value=100,
            value=st.session_state.manual_fetch_count,
            step=1
        )

        if st.button("Fetch Manually"):
            # This new call is only for messages where sent_while_away=1 & delivered=0
            resp = self.client.send_request(
                "fetch_messages",
                {"num_messages": st.session_state.manual_fetch_count}
            )
            if resp and resp.get("data", {}).get("status") == "ok":
                new_msgs = resp.get("data", {}).get("messages", [])
                existing_ids = {m["id"] for m in st.session_state.all_messages}
                added_count = 0
                for m in new_msgs:
                    if m["id"] not in existing_ids:
                        st.session_state.all_messages.append(m)
                        added_count += 1
                # You might also adjust st.session_state.unread_count here if desired
                st.success(f"Fetched {added_count} offline message(s).")
            else:
                st.error("Manual fetch failed or returned an error.")

        # Now display all messages in st.session_state.all_messages
        # with checkboxes for multi-select deletion:
        if st.session_state.all_messages:
            sorted_msgs = sorted(
                st.session_state.all_messages,
                key=lambda x: x.get("id", 0)
            )
            st.markdown("### Messages in your inbox:")

            selected_msg_ids = []

            for msg in sorted_msgs:
                cols = st.columns([0.07, 0.93])
                with cols[0]:
                    selected = st.checkbox("", key=f"select_{msg['id']}")
                with cols[1]:
                    st.markdown(
                        f"**ID:** {msg['id']} | **From:** {msg.get('sender')}"
                    )
                    st.markdown(
                        f"<div style='padding: 0.5rem 0;'>{msg.get('content')}</div>",
                        unsafe_allow_html=True
                    )
                st.markdown("---")
                if selected:
                    selected_msg_ids.append(msg["id"])

            # Button to delete all selected messages at once
            if st.button("Delete Selected"):
                if not selected_msg_ids:
                    st.warning("No messages selected for deletion.")
                else:
                    del_resp = self.client.send_request(
                        "delete_messages",
                        {"message_ids_to_delete": selected_msg_ids}
                    )
                    if del_resp and del_resp.get("data", {}).get("status") == "ok":
                        st.success(f"Deleted {len(selected_msg_ids)} message(s).")
                        # Remove them from local memory
                        st.session_state.all_messages = [
                            m for m in st.session_state.all_messages
                            if m["id"] not in selected_msg_ids
                        ]
                        # After deletion, you could re-call send_all_messages_to_client
                        # or fetch_messages if you want to refresh, but let's omit for brevity.
                    else:
                        st.error("Failed to delete selected messages.")
        else:
            st.info("No messages in your inbox. The app will automatically check every 5s.")

    def show_logout_page(self):
        """
        Shows a logout button, which invalidates the session in the server
        and resets local state.
        """
        if st.button("Logout"):
            response = self.client.send_request("logout", {})
            if response and response.get("data", {}).get("status") == "ok":
                st.success("Logged out.")
                st.session_state.logged_in = False
                st.session_state.username = ""
                if "socket" in st.session_state:
                    st.session_state["socket"].close()
                    del st.session_state["socket"]
                st.experimental_rerun()
            else:
                st.error(response.get("data", {}).get("msg", "Logout failed."))

    def run_app(self):
        """
        Main entry point for the Streamlit application.
        Routes to the appropriate page based on whether or not the user is logged in.
        """
        # Apply custom CSS
        self.apply_custom_css()

        st.title("Chat Application (JSON Protocol)")

        # If user is logged in, show user info and navigation
        if st.session_state.logged_in:
            st.sidebar.markdown(f"**User: {st.session_state.username}**")
            st.sidebar.markdown(f"**Unread Messages: {st.session_state.unread_count}**")

            menu = st.sidebar.radio("Navigation", ["Home", "Send Message", "Inbox", "Logout"])

            if menu == "Home":
                self.show_home_page()
            elif menu == "Send Message":
                self.show_send_message_page()
            elif menu == "Inbox":
                self.show_inbox_page()
            elif menu == "Logout":
                self.show_logout_page()

        else:
            # User is not logged in -> Show login/signup
            self.show_login_or_signup_page()


# -----------------------------------------------------------------------------
# Actually run the app (Streamlit entry point)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app = StreamlitChatApp(server_host="127.0.0.1", server_port=5555)
    app.run_app()