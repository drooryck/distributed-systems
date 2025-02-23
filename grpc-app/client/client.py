#!/usr/bin/env python3
import streamlit as st
import socket
import json
import hashlib
import struct  # For packing/unpacking the 4-byte length prefix
import time
import argparse

from streamlit_autorefresh import st_autorefresh
import sys, os

# Adjust import to your protocol's actual location
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from protocol.protocol import Message, JSONProtocolHandler, CustomProtocolHandler

###############################################################################
# ChatServerClient
###############################################################################
class ChatServerClient:
    """
    Encapsulates server connection behavior using a custom or JSON protocol.
    All client→server messages are requests (is_response=False);
    the server replies with is_response=True.
    """

    def __init__(self, server_host, server_port, protocol):
        self.server_host = server_host
        self.server_port = server_port
        if protocol == "json":
            self.protocol_handler = JSONProtocolHandler()
        else:
            self.protocol_handler = CustomProtocolHandler()

    def _get_socket(self):
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

    def send_request(self, msg_type, data=None):
        """
        Send a request (is_response=False) to the server
        and read exactly one response (is_response=True).
        """
        sock = self._get_socket()
        if not sock:
            return None
        try:
            message = Message(msg_type, data or {})
            self.protocol_handler.send(sock, message, is_response=False)
            response = self.protocol_handler.receive(sock)
            return response.data if response else None
        except Exception as e:
            st.error(f"Error communicating with server: {e}")
            return None

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()


###############################################################################
# StreamlitChatApp
###############################################################################
class StreamlitChatApp:
    """
    Main application class for our Streamlit-based Chat App.
    Two-step approach for offline messages:
      - "fetch_away_msgs(limit=N)" => partial/manual fetch of messages that were not delivered immediately.
      - "send_messages_to_client" => auto-deliver only messages marked for immediate delivery.
      
    Also includes ephemeral messages in the UI:
      - When new online messages arrive automatically,
      - When offline messages are manually fetched (partial fetching).

    Provides local, case-wise logic for common user actions and errors.

    Data in st.session_state is limited to:
      - logged_in, username, inbox_page (so the user remains on the same page in the inbox)
    """

    def __init__(self, server_host="127.0.0.1", server_port=5555, protocol="json"):
        self.server_host = server_host
        self.server_port = server_port
        self.client = ChatServerClient(server_host, server_port, protocol)
        self._init_session_state()

    def _init_session_state(self):
        # Persistent across pages
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False
        if "username" not in st.session_state:
            st.session_state.username = ""
        # we need the current page we are on in our inbox, because we cannot
        # expect the server to remember what page we are on and only deliver
        # us the messages from those pages
        if "inbox_page" not in st.session_state:
            st.session_state.inbox_page = 0

    def apply_custom_css(self):
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

    ###########################################################################
    # Login / Signup
    ###########################################################################
    def show_login_or_signup_page(self):
        st.header("Login or Create Account")
        action = st.radio("Select Action", ["Login", "Create Account"])
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button(action):
            if not username or not password:
                st.error("Please enter both username and password.")
                return

            hashed_pw = self.client.hash_password(password)

            if action == "Login":
                # Attempt login
                resp = self.client.send_request("login", {"username": username, "password": hashed_pw})
                if not resp:
                    st.error("No response from server.")
                    return
                if resp.get("status") == "ok":
                    st.success("Logged in successfully!")
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Wrong password.")

            else:  # "Create Account"
                signup_resp = self.client.send_request("signup", {"username": username, "password": hashed_pw})
                print(signup_resp)
                if not signup_resp:
                    st.error("No response from server.")
                    return
                if signup_resp.get("status") != "ok":
                    st.error(signup_resp.get("msg", "Account creation failed."))
                    return

                # 3) Auto-login
                login_resp = self.client.send_request("login", {"username": username, "password": hashed_pw})
                # Should not happen, but just in case
                if not login_resp or login_resp.get("status") != "ok":
                    st.error("Account created but auto-login failed.")
                    return

                st.success("Account created and logged in successfully!")
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()

    ###########################################################################
    # Home Page
    ###########################################################################
    def show_home_page(self):
        st.header("Welcome!")
        resp = self.client.send_request("count_unread", {})
        if resp and resp.get("status") == "ok":
            unread_count = resp.get("unread_count", 0)
        st.write(f"You have {unread_count} unread message(s).")
        st.info("Use the sidebar to navigate to Send Message, Inbox, List Accounts, Delete Account, or Logout.")

    ###########################################################################
    # Send Message
    ###########################################################################
    def show_send_message_page(self):
        st.header("Send a Message")
        recipient = st.text_input("Recipient Username")
        message_text = st.text_area("Message")

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
            if not resp:
                st.error("No response from server.")
                return
            if resp.get("status") == "ok":
                st.success("Message sent!")
            else:
                st.error("Message send failure.")

 

    ###########################################################################
    # Inbox
    ###########################################################################
    def show_inbox_page(self):
        st.header("Inbox")
        st_autorefresh(interval=5000, key="inbox_autorefresh")


        # this is an input field, it just defines the button on the page
        st.write("**Manually fetch offline messages**")
        manual_fetch_count = st.number_input(
            "How many offline messages to fetch at once?",
            min_value=1,
            max_value=100,
            value=5,  # default
            step=1
        )

        if st.button("Fetch Manually"):
            if manual_fetch_count <= 0:
                st.warning("Enter a positive number.")
                return
            
            away_resp = self.client.send_request("fetch_away_msgs", {"limit": manual_fetch_count})

            if not away_resp:
                st.error("No response from server.")
                return
            
            if away_resp and away_resp.get("status") == "ok":
                st.rerun() # or somethign like
            else:
                st.error("Manual fetch failed or returned an error.")


        # 3) Pagination uses st.session_state.inbox_page
        # NO IT BETTER NOT.

        MESSAGES_PER_PAGE = 10

        all_msgs = self.client.send_request("send_messages_to_client", {})

        if not all_msgs:
            st.error("No response from server.")
            return

        if all_msgs.get("status") == "ok":
            msgs = all_msgs.get("msg", [])
        else:
            st.error("Could not fetch messages.")

        total_msgs = len(msgs)
        if total_msgs == 0:
            st.info("No messages in your inbox yet.")
            return

        # at this stage we have 'msgs' which is a list of messages, and we have 'total_msgs'

        # the total number of pages at this moment that the user can scroll thru
        total_pages = (total_msgs + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE

        # set the inbox page to the last page if it is was greater than how many pages there will now be.
        st.session_state.inbox_page = min(st.session_state.inbox_page, total_pages - 1)
        st.session_state.inbox_page = max(st.session_state.inbox_page, 0)

        # writing the page number on the app.
        st.write(f"**Page {st.session_state.inbox_page + 1} / {total_pages}**")


        # bloody mess, no idea why this needs to be like this. maybe streamlit problem.
        colA, colB = st.columns(2)
        with colA:
            if total_pages > 1 and st.session_state.inbox_page > 0:
                if st.button("Prev Page"):
                    st.session_state.inbox_page -= 1
                    st.rerun()
        with colB:
            if total_pages > 1 and st.session_state.inbox_page < total_pages - 1:
                if st.button("Next Page"):
                    st.session_state.inbox_page += 1
                    st.rerun()

        # sorting by id implicitly sorts by time, because messages are assigned rising ids in the server.
        sorted_msgs = sorted(msgs, key=lambda x: x.get("id", 0), reverse=True)
        start_idx = st.session_state.inbox_page * MESSAGES_PER_PAGE
        end_idx = start_idx + MESSAGES_PER_PAGE
        page_msgs = sorted_msgs[start_idx:end_idx]

        if not page_msgs:
            st.info("No messages on this page.")
        else: # there are messages to show:
            st.markdown("### Messages in your inbox (latest first):")
            
            selected_msg_ids = []

            for cur_msg in page_msgs:
                cols = st.columns([0.07, 0.93])

                # load the checkbox for deleting messages
                with cols[0]:
                    selected = st.checkbox("selected", key=f"select_{cur_msg['id']}", label_visibility="collapsed")
                    if selected: # keep track of the checkbox-selected messages
                        selected_msg_ids.append(cur_msg["id"])

                # load the message itself, its id, its sender, and its content.
                with cols[1]:
                    st.markdown(f"**ID:** {cur_msg['id']} | **From:** {cur_msg.get('sender')}")
                    st.markdown(
                        f"<div style='padding: 0.5rem 0;'>{cur_msg.get('content')}</div>",
                        unsafe_allow_html=True
                    )
                st.markdown("---") # a little divider

            
            # logic for deleting all the messages that have been selected (are in a list)
            if st.button("Delete Selected"):
                if not selected_msg_ids:
                    st.warning("No messages selected for deletion.")
                else:
                    del_resp = self.client.send_request("delete_messages", {"message_ids_to_delete": selected_msg_ids})

                    if not del_resp:
                        st.error("No response from server.")
                        return
                    
                    if del_resp.get("status") == "ok":
                        st.success(f"Deleted {len(selected_msg_ids)} message(s).")
                        st.rerun()
                    else:
                        st.error("Deletion of selected messages failed.")

    ###########################################################################
    # List Accounts
    ###########################################################################
    def show_list_accounts_page(self):
        st.header("Search / List Accounts")

        # local input for search pattern, etc.
        account_pattern = st.text_input("Username Pattern (enter * for all)", "")
        account_count = st.number_input("Accounts per page", min_value=1, max_value=50, value=10, step=1)

        if st.button("Search / Refresh"):
            if not account_pattern.strip():
                st.warning("Username pattern cannot be empty.")
            else:
                self._perform_account_search(account_pattern, account_count)

    def _perform_account_search(self, pattern, count):
        """Search accounts (local pagination approach: we just do a single query)."""
        if pattern.strip() == "*":
            pattern = "%"

        data = {"pattern": pattern, "start": 0, "count": count}
        resp = self.client.send_request("list_accounts", data)
        if not resp:
            st.error("No response from server while listing accounts.")
            return

        if resp.get("status") == "ok":
            results = resp.get("users", [])
            if not results:
                st.warning("No accounts found matching your search criteria.")
                return
            st.markdown("**Matching Accounts**:")
            for acc in results:
                if isinstance(acc, (list, tuple)) and len(acc) == 2:
                    st.write(f"- ID {acc[0]} => {acc[1]}")
                else:
                    st.write(f"- {acc}")
        else:
            st.error("Could not list accounts.")

    ###########################################################################
    # Delete Account
    ###########################################################################
    def show_delete_account_page(self):
        st.header("Delete My Account")
        st.warning("This will permanently delete your account and all associated messages!")

        if st.button("Confirm Delete Account"):
            # 1) Confirm user still exists
            if not self._user_exists(st.session_state.username):
                st.error("Account does not exist.")
                return

            resp = self.client.send_request("delete_account", {})
            if not resp:
                st.error("No response from server.")
                return
            if resp.get("status") == "ok":
                st.success("Account deleted successfully!")
                st.session_state.logged_in = False
                st.session_state.username = ""
                if "socket" in st.session_state:
                    st.session_state["socket"].close()
                    del st.session_state["socket"]
                st.rerun()
            else:
                st.error("Failed to delete the account.")

    ###########################################################################
    # Logout
    ###########################################################################
    def show_logout_page(self):
        if st.button("Logout"):
            resp = self.client.send_request("logout", {})
            if not resp:
                st.error("No response from server.")
                return
            if resp.get("status") == "ok":
                st.success("Logged out.")
                st.session_state.logged_in = False
                st.session_state.username = ""
                if "socket" in st.session_state:
                    st.session_state["socket"].close()
                    del st.session_state["socket"]
                st.rerun()
            else:
                st.error("Logout was refused by the server.")

    ###########################################################################
    # Main run_app
    ###########################################################################
    def run_app(self):
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
# Entry point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JoChat Client")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server IP address")
    parser.add_argument("--port", type=int, default=5555, help="Server port")
    parser.add_argument("--protocol", type=str, choices=["json", "custom"], default="json",
                        help="Protocol to use: 'json' or 'custom'")
    args = parser.parse_args()

    app = StreamlitChatApp(server_host=args.host, server_port=args.port, protocol=args.protocol)
    app.run_app()