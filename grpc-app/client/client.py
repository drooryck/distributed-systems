#!/usr/bin/env python3
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import hashlib
import argparse

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import grpc
import chat_service_pb2
import chat_service_pb2_grpc


###############################################################################
# ChatServerClient
###############################################################################
class ChatServerClient:
    """
    Encapsulates server connection behavior using a custom or JSON protocol.
    All client→server messages are requests (is_response=False);
    the server replies with is_response=True.
    """

    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port

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

    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port
        self.client = ChatServerClient(server_host, server_port)
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
        if "auth_token" not in st.session_state:
            st.session_state.auth_token = ""
        if "account_page" not in st.session_state:
            st.session_state.account_page = 0

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
                resp = stub.Login(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))
                if not resp:
                    st.error("No response from server.")
                    return
                if resp.status == "ok":
                    st.success("Logged in successfully!")
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.auth_token = resp.auth_token
                    st.rerun()
                else:
                    st.error(str(resp.status)) # may deprecate server sending this error msg later.

            else:  # "Create Account"
                signup_resp = stub.Signup(chat_service_pb2.SignupRequest(username=username, password=hashed_pw))
                if not signup_resp:
                    st.error("No response from server.")
                    return
                if signup_resp.status != "ok":
                    st.error(signup_resp.msg if signup_resp.msg else "Account creation failed.")
                    return

                # 3) Auto-login
                login_resp = stub.Login(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))
                # Should not happen, but just in case
                if not login_resp or login_resp.status != "ok":
                    st.error("Account created but auto-login failed.")
                    return

                st.success("Account created and logged in successfully!")
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.auth_token = login_resp.auth_token
                st.rerun()

    ###########################################################################
    # Home Page
    ###########################################################################
    def show_home_page(self):
        st.header("Welcome!")
        resp = stub.CountUnread(chat_service_pb2.CountUnreadRequest(auth_token=st.session_state.auth_token))
        if resp and resp.status == "ok":
            unread_count = resp.unread_count if resp.unread_count else 0
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

          
            # resp = self.client.send_request("send_message", data)
            resp = stub.SendMessage(chat_service_pb2.SendMessageRequest(auth_token=st.session_state.auth_token, recipient=recipient, content=message_text))
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.success("Message sent!")
            else:
                st.error("Message send failure.")

 

        ###########################################################################
        # Inbox
        ###########################################################################
    def show_inbox_page(self):
        st.header("Inbox")
        st_autorefresh(interval=5000, key="inbox_autorefresh")

        # (A) Manual Fetch for Offline Messages (if you want to keep that)
        st.write("**Manually fetch offline messages**")
        manual_fetch_count = st.number_input(
            "How many offline messages to fetch at once?",
            min_value=1,
            max_value=100,
            value=5,
            step=1
        )
        if st.button("Fetch Manually"):
            if manual_fetch_count <= 0:
                st.warning("Enter a positive number.")
                return

            # This is your existing "FetchAwayMsgs"
            away_resp = stub.FetchAwayMsgs(
                chat_service_pb2.FetchAwayMsgsRequest(
                    limit=manual_fetch_count,
                    auth_token=st.session_state.auth_token
                )
            )
            if not away_resp:
                st.error("No response from server.")
                return
            if away_resp.status == "ok":
                # We'll refresh the inbox
                st.rerun()
            else:
                st.error("Manual fetch failed or returned an error.")

        # (B) Use st.session_state.inbox_page for paging
        if "inbox_page" not in st.session_state:
            st.session_state.inbox_page = 0

        MESSAGES_PER_PAGE = 10
        current_page = st.session_state.inbox_page
        start_offset = current_page * MESSAGES_PER_PAGE

        # (C) Request messages from the server with the desired offset/limit
        list_resp = stub.ListMessages(
            chat_service_pb2.ListMessagesRequest(
                auth_token=st.session_state.auth_token,
                start=start_offset,
                count=MESSAGES_PER_PAGE
            )
        )
        if not list_resp:
            st.error("No response from server.")
            return

        if list_resp.status != "ok":
            st.error(f"Could not fetch messages: {list_resp.msg}")
            return

        msgs = list_resp.messages  # repeated ChatMessage
        total_msgs = list_resp.total_count

        if total_msgs == 0:
            st.info("No messages in your inbox yet.")
            return

        # (D) Compute how many pages we have, ensure current_page is valid
        total_pages = (total_msgs + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE
        # Make sure we don't go out of range
        if current_page >= total_pages:
            st.session_state.inbox_page = max(0, total_pages - 1)
            st.rerun()

        st.write(f"**Page {current_page + 1} / {total_pages}**")

        # (E) Render pagination buttons

        colA, colB = st.columns(2)
        with colA:
            if current_page > 0:
                if st.button("Prev Page"):
                    st.session_state.inbox_page -= 1
                    st.rerun()
        with colB:
            if current_page < total_pages - 1:
                if st.button("Next Page"):
                    st.session_state.inbox_page += 1
                    st.rerun()

        ### F: SHOW THE MESSAGES
        if not msgs:
            # Could happen if the offset >= total_msgs
            st.info("No messages on this page.")
            return

        st.markdown("### Messages in your inbox (newest first):")

        selected_msg_ids = []

        for cur_msg in msgs:
            cols = st.columns([0.07, 0.93])
            with cols[0]:
                selected = st.checkbox(
                    "selected",
                    key=f"select_{cur_msg.id}",
                    label_visibility="collapsed"
                )
                if selected:
                    selected_msg_ids.append(cur_msg.id)
            with cols[1]:
                st.markdown(f"**ID:** {cur_msg.id} | **From:** {cur_msg.sender}")
                st.markdown(
                    f"<div style='padding: 0.5rem 0;'>{cur_msg.content}</div>",
                    unsafe_allow_html=True
                )
            st.markdown("---")

        # (G) Delete Selected
        if st.button("Delete Selected"):
            if not selected_msg_ids:
                st.warning("No messages selected for deletion.")
            else:
                del_resp = stub.DeleteMessages(
                    chat_service_pb2.DeleteMessagesRequest(
                        auth_token=st.session_state.auth_token,
                        message_ids_to_delete=selected_msg_ids
                    )
                )
                if not del_resp:
                    st.error("No response from server.")
                    return
                if del_resp.status == "ok":
                    st.success(f"Deleted {len(selected_msg_ids)} message(s).")
                    # reload this page
                    st.rerun()
                else:
                    st.error("Deletion of selected messages failed.")


    ###########################################################################
    # List Accounts
    ###########################################################################
    def show_list_accounts_page(self):
        st.header("Search / List Accounts")

        # Initialize pagination state if not present
        if "account_page" not in st.session_state:
            st.session_state.account_page = 0

        # 1) Gather user inputs
        pattern_input = st.text_input("Username Pattern (enter '*' for all)", "")
        accounts_per_page = st.number_input(
            "Accounts per page",
            min_value=1,
            max_value=50,
            value=10,
            step=1
        )

        # 2) If user clicks "Search / Refresh," reset to page 0
        if st.button("Search / Refresh"):
            st.session_state.account_page = 0

        # 3) Convert '*' → '%' for sql, and strip
        pattern = pattern_input.strip()
        if pattern == "*":
            pattern = "%"
        if not pattern:
            st.info("Enter a pattern (or '*') and click 'Search / Refresh'.")
            return

        # 4) First, fetch total number of matching accounts
        #    by requesting a large count (or you could define a dedicated Count API).
        total_resp = stub.ListAccounts(
            chat_service_pb2.ListAccountsRequest(
                auth_token=st.session_state.auth_token,
                pattern=pattern,
                start=0,
                count=1000  # effectively "no limit"
            )
        )
        if not total_resp or total_resp.status != "ok":
            st.error(f"Could not list accounts. Server status: {getattr(total_resp, 'status', 'no response')}")
            return

        total_accounts = len(total_resp.users)
        if total_accounts == 0:
            st.warning("No accounts found matching your search criteria.")
            return

        # 5) Now fetch only the subset for the current page
        start_offset = st.session_state.account_page * accounts_per_page
        page_resp = stub.ListAccounts(
            chat_service_pb2.ListAccountsRequest(
                auth_token=st.session_state.auth_token,
                pattern=pattern,
                start=start_offset,
                count=accounts_per_page
            )
        )
        if not page_resp or page_resp.status != "ok":
            st.error(f"Could not list accounts (page). Server status: {getattr(page_resp, 'status', 'no response')}")
            return

        # 6) Display the accounts for this page
        accounts_on_page = page_resp.users
        st.markdown("**Matching Accounts (this page):**")
        for acc in accounts_on_page:
            st.write(f"- {acc.username}")

        # 7) Pagination controls
        total_pages = (total_accounts + accounts_per_page - 1) // accounts_per_page
        current_page = st.session_state.account_page + 1

        st.write(f"**Page {current_page} / {total_pages}**")

        col1, col2 = st.columns(2)
        with col1:
            # "Prev Page"
            if current_page > 1:
                if st.button("Prev Accounts"):
                    st.session_state.account_page -= 1
                    st.rerun()

        with col2:
            # "Next Page"
            if current_page < total_pages:
                if st.button("Next Accounts"):
                    st.session_state.account_page += 1
                    st.rerun()


    ###########################################################################
    # Delete Account
    ###########################################################################
    def show_delete_account_page(self):
        st.header("Delete My Account")
        st.warning("This will permanently delete your account and all associated messages!")

        if st.button("Confirm Delete Account"):
            resp = stub.DeleteAccount(chat_service_pb2.EmptyRequest(auth_token=st.session_state.auth_token))
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.success("Account deleted successfully!")
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.rerun()
            else:
                st.error("Failed to delete the account.")

    ###########################################################################
    # Logout
    ###########################################################################
    def show_logout_page(self):
        if st.button("Logout"):
            resp = stub.Logout(chat_service_pb2.EmptyRequest(auth_token=st.session_state.auth_token))
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.success("Logged out.")
                st.session_state.logged_in = False
                st.session_state.username = ""
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
    # Setup connection
    channel = grpc.insecure_channel("127.0.0.1:50051")
    stub = chat_service_pb2_grpc.ChatServiceStub(channel)
    parser = argparse.ArgumentParser(description="JoChat Client")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server IP address")
    parser.add_argument("--port", type=int, default=5555, help="Server port")

    args = parser.parse_args()

    app = StreamlitChatApp(server_host=args.host, server_port=args.port)
    app.run_app()