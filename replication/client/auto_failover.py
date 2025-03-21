#!/usr/bin/env python3
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import hashlib
import argparse
import sys, os
import grpc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import chat_service_pb2
import chat_service_pb2_grpc

###############################################################################
# ChatServerClient
###############################################################################
class ChatServerClient:
    """
    Encapsulates server connection behavior for an AUTOMATIC FAILOVER version.
    
    - We store multiple server addresses.
    - On each request, we try the 'current' server first. If it fails, we iterate
      through the list to find a working server. We then set that as 'current'.
    - This approach can tolerate up to 2 servers going down, as long as at least
      one server remains functional.
    """

    def __init__(self, server_addresses):
        """
        server_addresses: list of possible gRPC addresses (e.g. ["127.0.0.1:50051", "127.0.0.1:50052"]).
        We'll attempt them in order to find a working server.
        """
        self.server_addresses = server_addresses
        self.current_idx = 0  # start with the first address
        self.stub = None
        if not server_addresses:
            raise ValueError("No server addresses provided.")
        self._connect_stub(self.server_addresses[self.current_idx])

    def _connect_stub(self, address):
        """(Re)connect to the given address and store the stub."""
        channel = grpc.insecure_channel(address)
        self.stub = chat_service_pb2_grpc.ChatServiceStub(channel)

    def _try_stub_call(self, func, *args, **kwargs):
        """
        Attempt the given stub function. If it fails, we move to the next server.
        Returns the response or None if all servers fail.
        """
        num_servers = len(self.server_addresses)
        attempts = 0

        while attempts < num_servers:
            current_address = self.server_addresses[self.current_idx]
            try:
                # Make the RPC call
                return func(*args, **kwargs)
            except grpc.RpcError as rpc_err:
                st.warning(f"Server {current_address} failed with {rpc_err}. Trying next server.")
            except Exception as e:
                st.warning(f"Server {current_address} error: {e}. Trying next server.")
            
            # Move to the next server
            self.current_idx = (self.current_idx + 1) % num_servers
            self._connect_stub(self.server_addresses[self.current_idx])
            attempts += 1

        # If we exhaust the loop, all servers failed
        st.error("All servers appear to be down. Could not complete request.")
        return None

    # We wrap each RPC method to automatically fail over
    def signup(self, username, password):
        req = chat_service_pb2.SignupRequest(username=username, password=password)
        return self._try_stub_call(self.stub.Signup, req)

    def login(self, username, password):
        req = chat_service_pb2.LoginRequest(username=username, password=password)
        return self._try_stub_call(self.stub.Login, req)

    def logout(self, auth_token):
        req = chat_service_pb2.EmptyRequest(auth_token=auth_token)
        return self._try_stub_call(self.stub.Logout, req)

    def count_unread(self, auth_token):
        req = chat_service_pb2.CountUnreadRequest(auth_token=auth_token)
        return self._try_stub_call(self.stub.CountUnread, req)

    def send_message(self, auth_token, recipient, content):
        req = chat_service_pb2.SendMessageRequest(
            auth_token=auth_token,
            recipient=recipient,
            content=content
        )
        return self._try_stub_call(self.stub.SendMessage, req)

    def list_messages(self, auth_token, start, count):
        req = chat_service_pb2.ListMessagesRequest(
            auth_token=auth_token,
            start=start,
            count=count
        )
        return self._try_stub_call(self.stub.ListMessages, req)

    def fetch_away_msgs(self, auth_token, limit):
        req = chat_service_pb2.FetchAwayMsgsRequest(
            auth_token=auth_token,
            limit=limit
        )
        return self._try_stub_call(self.stub.FetchAwayMsgs, req)

    def list_accounts(self, auth_token, pattern, start, count):
        req = chat_service_pb2.ListAccountsRequest(
            auth_token=auth_token,
            pattern=pattern,
            start=start,
            count=count
        )
        return self._try_stub_call(self.stub.ListAccounts, req)

    def delete_messages(self, auth_token, message_ids):
        req = chat_service_pb2.DeleteMessagesRequest(
            auth_token=auth_token,
            message_ids_to_delete=message_ids
        )
        return self._try_stub_call(self.stub.DeleteMessages, req)

    def delete_account(self, auth_token):
        req = chat_service_pb2.EmptyRequest(auth_token=auth_token)
        return self._try_stub_call(self.stub.DeleteAccount, req)

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

###############################################################################
# StreamlitChatApp
###############################################################################
class StreamlitChatApp:
    """
    Main application class for our Streamlit-based Chat App.
    AUTOMATIC FAILOVER version: each request tries the current server; if it fails,
    we automatically switch to the next server in the list.
    """

    def __init__(self, server_addresses):
        self.server_addresses = server_addresses
        self.client = ChatServerClient(server_addresses)
        self._init_session_state()

    def _init_session_state(self):
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False
        if "username" not in st.session_state:
            st.session_state.username = ""
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
                resp = self.client.login(username, hashed_pw)
                if not resp:
                    st.error("No response from server (all servers down?).")
                    return
                if resp.status == "ok":
                    st.success("Logged in successfully!")
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.auth_token = resp.auth_token
                    st.rerun()
                else:
                    st.error(str(resp.status))

            else:  # "Create Account"
                signup_resp = self.client.signup(username, hashed_pw)
                if not signup_resp:
                    st.error("No response from server (all servers down?).")
                    return
                if signup_resp.status != "ok":
                    st.error(signup_resp.msg if signup_resp.msg else "Account creation failed.")
                    return
                # Auto-login
                login_resp = self.client.login(username, hashed_pw)
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
        resp = self.client.count_unread(st.session_state.auth_token)
        if resp and resp.status == "ok":
            unread_count = resp.unread_count if resp.unread_count else 0
        else:
            unread_count = 0
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
            resp = self.client.send_message(
                auth_token=st.session_state.auth_token,
                recipient=recipient,
                content=message_text
            )
            if not resp:
                st.error("No response from server (all servers down?).")
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
            away_resp = self.client.fetch_away_msgs(st.session_state.auth_token, manual_fetch_count)
            if not away_resp:
                st.error("No response from server (all servers down?).")
                return
            if away_resp.status == "ok":
                st.rerun()
            else:
                st.error("Manual fetch failed or returned an error.")

        if "inbox_page" not in st.session_state:
            st.session_state.inbox_page = 0
        MESSAGES_PER_PAGE = 10
        current_page = st.session_state.inbox_page
        start_offset = current_page * MESSAGES_PER_PAGE

        list_resp = self.client.list_messages(st.session_state.auth_token, start_offset, MESSAGES_PER_PAGE)
        if not list_resp:
            st.error("No response from server (all servers down?).")
            return
        if list_resp.status != "ok":
            st.error(f"Could not fetch messages: {list_resp.msg}")
            return

        msgs = list_resp.messages
        total_msgs = list_resp.total_count

        if total_msgs == 0:
            st.info("No messages in your inbox yet.")
            return

        total_pages = (total_msgs + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE
        if current_page >= total_pages:
            st.session_state.inbox_page = max(0, total_pages - 1)
            st.rerun()

        st.write(f"**Page {current_page + 1} / {total_pages}**")

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

        if st.button("Delete Selected"):
            if not selected_msg_ids:
                st.warning("No messages selected for deletion.")
            else:
                del_resp = self.client.delete_messages(st.session_state.auth_token, selected_msg_ids)
                if not del_resp:
                    st.error("No response from server (all servers down?).")
                    return
                if del_resp.status == "ok":
                    st.success(f"Deleted {len(selected_msg_ids)} message(s).")
                    st.rerun()
                else:
                    st.error("Deletion of selected messages failed.")

    ###########################################################################
    # List Accounts
    ###########################################################################
    def show_list_accounts_page(self):
        st.header("Search / List Accounts")
        if "account_page" not in st.session_state:
            st.session_state.account_page = 0

        pattern_input = st.text_input("Username Pattern (enter '*' for all)", "")
        accounts_per_page = st.number_input(
            "Accounts per page",
            min_value=1,
            max_value=50,
            value=10,
            step=1
        )

        if st.button("Search / Refresh"):
            st.session_state.account_page = 0

        pattern = pattern_input.strip()
        if pattern == "*":
            pattern = "%"
        if not pattern:
            st.info("Enter a pattern (or '*') and click 'Search / Refresh'.")
            return

        total_resp = self.client.list_accounts(st.session_state.auth_token, pattern, 0, 1000)
        if not total_resp or total_resp.status != "ok":
            st.error(f"Could not list accounts. Server status: {getattr(total_resp, 'status', 'no response')}")
            return

        total_accounts = len(total_resp.users)
        if total_accounts == 0:
            st.warning("No accounts found matching your search criteria.")
            return

        current_page = st.session_state.account_page
        start_offset = current_page * accounts_per_page

        page_resp = self.client.list_accounts(st.session_state.auth_token, pattern, start_offset, accounts_per_page)
        if not page_resp or page_resp.status != "ok":
            st.error(f"Could not list accounts (page). Server status: {getattr(page_resp, 'status', 'no response')}")
            return

        accounts_on_page = page_resp.users
        st.markdown("**Matching Accounts (this page):**")
        for acc in accounts_on_page:
            st.write(f"- {acc.username}")

        total_pages = (total_accounts + accounts_per_page - 1) // accounts_per_page
        st.write(f"**Page {current_page + 1} / {total_pages}**")

        col1, col2 = st.columns(2)
        with col1:
            if current_page > 0:
                if st.button("Prev Accounts"):
                    st.session_state.account_page -= 1
                    st.rerun()
        with col2:
            if current_page < total_pages - 1:
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
            resp = self.client.delete_account(st.session_state.auth_token)
            if not resp:
                st.error("No response from server (all servers down?).")
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
            resp = self.client.logout(st.session_state.auth_token)
            if not resp:
                st.error("No response from server (all servers down?).")
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
        st.title("JoChat (Automatic Failover Version)")

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
    parser = argparse.ArgumentParser(description="JoChat Client (Automatic Failover)")
    parser.add_argument("--servers", type=str, default="127.0.0.1:50051",
                        help="Comma-separated list of possible servers (e.g. '127.0.0.1:50051,127.0.0.1:50052')")
    args = parser.parse_args()

    server_list = [s.strip() for s in args.servers.split(",") if s.strip()]
    if not server_list:
        print("No server addresses provided. Exiting.")
        sys.exit(1)

    app = StreamlitChatApp(server_list)
    app.run_app()
