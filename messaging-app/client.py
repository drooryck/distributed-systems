#!/usr/bin/env python3
import streamlit as st
import socket
import json
import hashlib
import struct  # For packing/unpacking the 4-byte length prefix
import time
import argparse

# pip install streamlit-autorefresh
from streamlit_autorefresh import st_autorefresh

from protocol import Message, JSONProtocolHandler, CustomProtocolHandler


# for all functions: make sure you understand these lines (e.g. see docs)
class ChatServerClient:
    """
    Encapsulates server connection behavior and JSON communication protocol
    (length-prefixed JSON messages).
    """

    def __init__(self, server_host="10.250.120.214", server_port=5555, protocol="json"):
        self.server_host = server_host
        self.server_port = server_port
        self.protocol = protocol
        if protocol == "json":
            self.protocol_handler = JSONProtocolHandler()
        else:
            self.protocol_handler = CustomProtocolHandler()


    def _get_socket(self):
        """
        Get (or create) a persistent socket connection stored in Streamlit's session state.
        """
        if "socket" not in st.session_state:
            try:
                # make sure you understand these lines (e.g. see docs)
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
        Send a request to the server using the selected protocol.
        """
        sock = self._get_socket()
        if not sock:
            return None
        try:
            message = Message(msg_type, data)
            self.protocol_handler.send(sock, message)

            # Receive response
            response = self.protocol_handler.receive(sock)
            #print(f"[DEBUG] Raw response received from server: {response}, {self.protocol_handler}")
            return response.data if response else None
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
    Two-step approach for offline messages:
      - "fetch_away_msgs(limit=N)" => partial/manual fetch of messages that were not delivered immediately.
      - "send_messages_to_client" => auto-deliver only messages marked for immediate delivery.
      
    Also includes ephemeral messages in the UI:
      - When new online messages arrive automatically,
      - When offline messages are manually fetched (partial fetching).
    """

    def __init__(self, server_host="10.250.120.214", server_port=5555, protocol="json"):
        self.server_host = server_host
        self.server_port = server_port
        self.client = ChatServerClient(server_host, server_port, protocol)
        self._initialize_session_state()

    def _initialize_session_state(self):
        """
        Initialize any session_state variables if they do not exist yet.
        """
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False
        if "all_messages" not in st.session_state:
            st.session_state.all_messages = []
        if "unread_count" not in st.session_state:
            st.session_state.unread_count = 0
        if "username" not in st.session_state:
            st.session_state.username = ""
        if "inbox_page" not in st.session_state:
            st.session_state.inbox_page = 0
        if "manual_fetch_count" not in st.session_state:
            st.session_state.manual_fetch_count = 5

        # For listing accounts
        if "account_pattern" not in st.session_state:
            st.session_state.account_pattern = ""
        if "account_start" not in st.session_state:
            st.session_state.account_start = 0
        if "account_count" not in st.session_state:
            st.session_state.account_count = 10
        if "found_accounts" not in st.session_state:
            st.session_state.found_accounts = []

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

    def _update_unread_count(self):
        """
        Calls 'count_unread' on the server to get the number of messages 
        that have not yet been delivered (to_deliver==0) and sets st.session_state.unread_count.
        """
        resp = self.client.send_request("count_unread", {})
        if resp and resp.get("status") == "ok":
            st.session_state.unread_count = resp.get("unread_count", 0)

    def show_login_or_signup_page(self):
        """
        Page to login or create an account.
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

                if response.get("status") == "ok":
                    st.success("Logged in successfully!")
                    # Clear any cached messages on new login
                    st.session_state.all_messages = []
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.unread_count = response.get("unread_count", 0)
                    # Immediately fetch any pending messages:
                    self._auto_fetch_inbox()
                    # Re-run script to update the UI
                    st.rerun()
                else:
                    st.error(response.get("msg", "Action failed."))


            else:  # Create Account
                signup_resp = self.client.send_request("signup", data)
                if signup_resp is None:
                    st.error("No response from server. Check that the server is running.")
                    return

                if not signup_resp.get("status") == "ok":
                    st.error(signup_resp.get("msg", "Action failed."))
                    return

                # Auto-login after successful creation
                login_resp = self.client.send_request("login", data)
                if not login_resp or login_resp.get("status") != "ok":
                    st.error("Account created but auto-login failed.")
                    return

                st.success("Account created and logged in successfully!")
                st.session_state.all_messages = []  # Clear cached messages
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.unread_count = login_resp.get("unread_count", 0)
                self._auto_fetch_inbox()
                st.rerun()

    def show_home_page(self):
        """
        Displays a simple home/landing page upon successful login.
        """
        st.header("Welcome!")
        st.write(f"You have {st.session_state.unread_count} unread message(s).")
        st.info("Use the sidebar to navigate to Send Message, Inbox, List Accounts, or Delete Account, or Logout.")

    def show_send_message_page(self):
        """
        Page to send a new message to another user.
        (If the user is logged in, the server sets to_deliver=1 for immediate delivery;
         otherwise, the message will be stored for later manual fetching.)
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
            resp = self.client.send_request("send_message", data)
            if resp is None:
                st.error("No response from server. Check that the server is running.")
            elif resp.get("status") != "ok":
                st.error(resp.get("data", {}).get("msg", "Failed to send message."))
            else:
                st.success("Message sent!")
                # Update unread count if needed
                self._update_unread_count()

    def _auto_fetch_inbox(self):
        """
        Called every 5 seconds to fetch messages that arrived while the user was logged in.
        Only fetches **new** messages that were marked for immediate delivery (to_deliver==1).
        """
        resp = self.client.send_request("send_messages_to_client", {})
        if resp and resp.get("status") == "ok":
            returned_msgs = resp.get("msg", [])
            existing_ids = {m["id"] for m in st.session_state.all_messages}
            newly_added = 0
            
            # Add only new messages that are not already in the inbox.
            for m in returned_msgs:
                if m["id"] not in existing_ids:
                    st.session_state.all_messages.append(m)
                    newly_added += 1
            
            if newly_added > 0:
                st.info(f"Auto-delivered {newly_added} new message(s).")

            self._update_unread_count()

    def show_inbox_page(self):
        """
        The main inbox page.

          1) Auto-fetch every 5s for new messages (to_deliver==1)
          2) Manual fetch for offline messages (to_deliver==0)
          3) Display messages in LIFO order, 10 per page.
        """
        st.header("Inbox")

        # Auto-refresh every 5 seconds
        st_autorefresh(interval=5000, key="inbox_autorefresh")

        # Step 1: auto fetch for messages marked for immediate delivery.
        self._auto_fetch_inbox()

        st.write("**Manually fetch offline messages**")
        st.session_state.manual_fetch_count = st.number_input(
            "How many offline messages to fetch at once?",
            min_value=1,
            max_value=100,
            value=st.session_state.manual_fetch_count,
            step=1
        )

        # Step 2: manual fetch for offline messages (to_deliver==0)
        if st.button("Fetch Manually"):
            away_resp = self.client.send_request(
                "fetch_away_msgs",
                {"limit": st.session_state.manual_fetch_count}
            )
            if away_resp and away_resp.get("status") == "ok":
                new_away = away_resp.get("msg", [])
                if new_away:
                    existing_ids = {m["id"] for m in st.session_state.all_messages}
                    added_count = 0
                    for m in new_away:
                        if m["id"] not in existing_ids:
                            st.session_state.all_messages.append(m)
                            added_count += 1
                    st.success(f"Manually fetched {added_count} offline message(s).")
                    time.sleep(1)  # Prevent immediate rerun from wiping out success message
                    st.rerun()
                else:
                    st.info("No new offline messages were found.")
            else:
                st.error("Manual fetch failed or returned an error.")

        # Pagination
        MESSAGES_PER_PAGE = 10
        all_msgs = st.session_state.all_messages
        total_msgs = len(all_msgs)

        if total_msgs == 0:
            st.info("No messages in your inbox yet.")
            return

        total_pages = (total_msgs + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE

        # Next/Prev page controls
        colA, colB = st.columns(2)
        with colA:
            if st.button("Prev Page"):
                if st.session_state.inbox_page > 0:
                    st.session_state.inbox_page -= 1
        with colB:
            if st.session_state.inbox_page < total_pages - 1:
                if st.button("Next Page"):
                    st.session_state.inbox_page += 1

        st.write(f"**Page {st.session_state.inbox_page + 1} / {total_pages}**")

        # Sort messages in LIFO order
        sorted_msgs = sorted(all_msgs, key=lambda x: x.get("id", 0), reverse=True)
        start_idx = st.session_state.inbox_page * MESSAGES_PER_PAGE
        end_idx = start_idx + MESSAGES_PER_PAGE
        page_msgs = sorted_msgs[start_idx:end_idx]

        if page_msgs:
            st.markdown("### Messages in your inbox (latest first):")
            selected_msg_ids = []
            for msg in page_msgs:
                cols = st.columns([0.07, 0.93])
                with cols[0]:
                    selected = st.checkbox("", key=f"select_{msg['id']}", label_visibility="collapsed")
                with cols[1]:
                    st.markdown(f"**ID:** {msg['id']} | **From:** {msg.get('sender')}")
                    st.markdown(
                        f"<div style='padding: 0.5rem 0;'>{msg.get('content')}</div>",
                        unsafe_allow_html=True
                    )
                st.markdown("---")
                if selected:
                    selected_msg_ids.append(msg["id"])

            # Deletion
            if st.button("Delete Selected"):
                if not selected_msg_ids:
                    st.warning("No messages selected for deletion.")
                else:
                    del_resp = self.client.send_request(
                        "delete_messages",
                        {"message_ids_to_delete": selected_msg_ids}
                    )
                    if del_resp and del_resp.get("status") == "ok":
                        st.success(f"Deleted {len(selected_msg_ids)} message(s).")
                        # Remove deleted messages from local cache
                        st.session_state.all_messages = [
                            m for m in st.session_state.all_messages
                            if m["id"] not in selected_msg_ids
                        ]
                        self._auto_fetch_inbox()
                        st.rerun()
                    else:
                        st.error("Failed to delete selected messages.")
        else:
            st.info("No messages on this page.")

    def show_list_accounts_page(self):
        """
        A page that searches for user accounts by pattern, with basic pagination.
        If user enters '*', interpret that as '%'.
        """
        st.header("Search / List Accounts")

        # Local data to this function 
        st.session_state.account_pattern = st.text_input(
            "Username Pattern (enter * for all)",
            value=st.session_state.account_pattern
        )
        st.session_state.account_count = st.number_input(
            "Accounts per page",
            min_value=1,
            max_value=50,
            value=st.session_state.account_count,
            step=1
        )

        if st.button("Search / Refresh"):
            st.session_state.account_start = 0
            self._search_accounts()

        if st.session_state.found_accounts:
            st.markdown("**Matching Accounts**:")
            for acc in st.session_state.found_accounts:
                st.write(f"- {acc}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Prev Accounts") and st.session_state.account_start > 0:
                    st.session_state.account_start -= st.session_state.account_count
                    if st.session_state.account_start < 0:
                        st.session_state.account_start = 0
                    self._search_accounts()

            with col2:
                if len(st.session_state.found_accounts) == st.session_state.account_count:
                    if st.button("Next Accounts"):
                        st.session_state.account_start += st.session_state.account_count
                        self._search_accounts()
        else:
            st.info("No accounts found or no search performed yet.")

    def _search_accounts(self):
        """
        Helper function to call the server's 'list_accounts' action.
        If user enters '*', interpret that as '%'.
        """
        pattern = st.session_state.account_pattern.strip()
        if pattern == "*":
            pattern = "%"
        start = st.session_state.account_start
        count = st.session_state.account_count

        data = {
            "pattern": pattern,
            "start": start,
            "count": count
        }
        resp = self.client.send_request("list_accounts", data)
        if resp and resp.get("status") == "ok":
            user_list = resp.get("users", [])
            st.session_state.found_accounts = user_list
        else:
            st.error("Could not list accounts or no users found.")
            st.session_state.found_accounts = []

    def show_delete_account_page(self):
        """
        Page for the user to delete their own account. 
        Calls 'delete_account' server action.
        After success, logs them out and resets local state.
        """
        st.header("Delete My Account")
        st.warning("This will permanently delete your account and all associated messages!")

        if st.button("Confirm Delete Account"):
            resp = self.client.send_request("delete_account", {})
            if resp and resp.get("status") == "ok":
                st.success("Account deleted successfully!")
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.unread_count = 0
                st.session_state.all_messages = []
                if "socket" in st.session_state:
                    st.session_state["socket"].close()
                    del st.session_state["socket"]
                st.rerun()
            else:
                st.error("Failed to delete account, or you are not logged in.")

    def show_logout_page(self):
        """
        Shows a logout button, which invalidates the session in the server
        and resets local state.
        """
        if st.button("Logout"):
            response = self.client.send_request("logout", {})
            if response and response.get("status") == "ok":
                st.success("Logged out.")
                st.session_state.logged_in = False
                st.session_state.username = ""
                if "socket" in st.session_state:
                    st.session_state["socket"].close()
                    del st.session_state["socket"]
                st.rerun()
            else:
                st.error(response.get("msg", "Logout failed."))
                
                

    def run_app(self):
        """
        Main entry point for the Streamlit application.
        Routes to the appropriate page based on whether or not the user is logged in.
        """
        self.apply_custom_css()

        st.title("JoChat")

        if st.session_state.logged_in:
            st.sidebar.markdown(f"**User: {st.session_state.username}**")

            menu = st.sidebar.radio(
                "Navigation",
                ["Home", "Send Message", "Inbox", "List Accounts", "Delete Account", "Logout"]
            )

            if menu == "Home":
                self.show_home_page()
            elif menu == "Send Message":
                self.show_send_message_page()
            elif menu == "Inbox":
                self.show_inbox_page()
            elif menu == "List Accounts":
                self.show_list_accounts_page()
            elif menu == "Delete Account":
                self.show_delete_account_page()
            elif menu == "Logout":
                self.show_logout_page()
        else:
            self.show_login_or_signup_page()


# -----------------------------------------------------------------------------
# Actually run the app (Streamlit entry point)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JoChat Client")
    parser.add_argument("--host", type=str, default="10.250.120.214", help="Server IP address (default: 10.250.120.214)")
    parser.add_argument("--port", type=int, default=5555, help="Server port (default: 5555)")
    parser.add_argument("--protocol", type=str, choices=["json", "custom"], default="json",
                        help="Protocol to use: 'json' or 'custom' (default: json)")

    args = parser.parse_args()

    # Pass the chosen protocol dynamically
    app = StreamlitChatApp(server_host=args.host, server_port=args.port, protocol=args.protocol)
    app.run_app()
