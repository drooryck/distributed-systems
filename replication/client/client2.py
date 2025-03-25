#!/usr/bin/env python3
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import hashlib
import argparse
import sys, os
import grpc

# Adjust the path if needed so that the proto-generated files are found.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import chat_service_pb2
import chat_service_pb2_grpc

###############################################################################
# ChatServerClient (Automatic Failover with a list of servers)
###############################################################################
class ChatServerClient:
    """
    This client stores a list of server addresses and attempts automatic failover.
    It tries the current server; if the RPC call fails, it cycles through the list.
    """
    def __init__(self, server_addresses):
        if not server_addresses:
            raise ValueError("No server addresses provided.")
        self.server_addresses = server_addresses
        self.current_idx = 0
        self.stub = None
        self._connect_stub(self.server_addresses[self.current_idx])

    def _connect_stub(self, address):
        channel = grpc.insecure_channel(address)
        self.stub = chat_service_pb2_grpc.ChatServiceStub(channel)

    def _try_stub_call(self, func, *args, **kwargs):
        num_servers = len(self.server_addresses)
        attempts = 0
        while attempts < num_servers:
            try:
                return func(*args, **kwargs)
            except grpc.RpcError as e:
                st.warning(f"Server {self.server_addresses[self.current_idx]} failed: {e}. Trying next server.")
                self.current_idx = (self.current_idx + 1) % num_servers
                self._connect_stub(self.server_addresses[self.current_idx])
                attempts += 1
        st.error("All servers are down.")
        return None

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
        req = chat_service_pb2.SendMessageRequest(auth_token=auth_token, recipient=recipient, content=content)
        return self._try_stub_call(self.stub.SendMessage, req)

    def list_messages(self, auth_token, start, count):
        req = chat_service_pb2.ListMessagesRequest(auth_token=auth_token, start=start, count=count)
        return self._try_stub_call(self.stub.ListMessages, req)

    def fetch_away_msgs(self, auth_token, limit):
        req = chat_service_pb2.FetchAwayMsgsRequest(auth_token=auth_token, limit=limit)
        return self._try_stub_call(self.stub.FetchAwayMsgs, req)

    def list_accounts(self, auth_token, pattern, start, count):
        req = chat_service_pb2.ListAccountsRequest(auth_token=auth_token, pattern=pattern, start=start, count=count)
        return self._try_stub_call(self.stub.ListAccounts, req)

    def delete_messages(self, auth_token, message_ids):
        req = chat_service_pb2.DeleteMessagesRequest(auth_token=auth_token, message_ids_to_delete=message_ids)
        return self._try_stub_call(self.stub.DeleteMessages, req)

    def delete_account(self, auth_token):
        req = chat_service_pb2.EmptyRequest(auth_token=auth_token)
        return self._try_stub_call(self.stub.DeleteAccount, req)

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()


###############################################################################
# StreamlitChatApp (Automatic Failover with Server List Display)
###############################################################################
class StreamlitChatApp:
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
            body { font-family: sans-serif; }
            </style>
            """,
            unsafe_allow_html=True
        )

    def show_server_list(self):
        st.sidebar.markdown("### Available Servers")
        for server in self.client.server_addresses:
            st.sidebar.write(server)
        st.sidebar.markdown(f"**Current Server:** {self.client.server_addresses[self.client.current_idx]}")

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
                    st.error("No response from server.")
                    return
                if resp.status == "ok":
                    st.success("Logged in successfully!")
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.auth_token = resp.auth_token
                    st.rerun()
                else:
                    st.error(resp.msg)
            else:
                signup_resp = self.client.signup(username, hashed_pw)
                if not signup_resp:
                    st.error("No response from server.")
                    return
                if signup_resp.status != "ok":
                    st.error(signup_resp.msg)
                    return
                login_resp = self.client.login(username, hashed_pw)
                if not login_resp or login_resp.status != "ok":
                    st.error("Account created but auto-login failed.")
                    return
                st.success("Account created and logged in!")
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.auth_token = login_resp.auth_token
                st.rerun()

    def show_home_page(self):
        st.header("Welcome!")
        resp = self.client.count_unread(st.session_state.auth_token)
        unread_count = resp.unread_count if resp and resp.status == "ok" else 0
        st.write(f"You have {unread_count} unread messages.")
        st.info("Use the sidebar to navigate.")

    def show_send_message_page(self):
        st.header("Send a Message")
        recipient = st.text_input("Recipient Username")
        message_text = st.text_area("Message")
        if st.button("Send"):
            if not recipient or not message_text:
                st.error("Please fill in all fields.")
                return
            resp = self.client.send_message(st.session_state.auth_token, recipient, message_text)
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.success("Message sent!")
            else:
                st.error("Message failed to send.")

    def show_inbox_page(self):
        st.header("Inbox")
        st_autorefresh(interval=5000, key="inbox_autorefresh")
        manual_fetch_count = st.number_input("Offline messages to fetch", min_value=1, max_value=100, value=5, step=1)
        if st.button("Fetch Manually"):
            if manual_fetch_count <= 0:
                st.warning("Enter a positive number.")
                return
            resp = self.client.fetch_away_msgs(st.session_state.auth_token, manual_fetch_count)
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.rerun()
            else:
                st.error("Manual fetch error.")
        if "inbox_page" not in st.session_state:
            st.session_state.inbox_page = 0
        MESSAGES_PER_PAGE = 10
        current_page = st.session_state.inbox_page
        start_offset = current_page * MESSAGES_PER_PAGE
        list_resp = self.client.list_messages(st.session_state.auth_token, start_offset, MESSAGES_PER_PAGE)
        if not list_resp:
            st.error("No response from server.")
            return
        if list_resp.status != "ok":
            st.error(list_resp.msg)
            return
        msgs = list_resp.messages
        total_msgs = list_resp.total_count
        if total_msgs == 0:
            st.info("No messages in your inbox.")
            return
        total_pages = (total_msgs + MESSAGES_PER_PAGE - 1) // MESSAGES_PER_PAGE
        if current_page >= total_pages:
            st.session_state.inbox_page = max(0, total_pages - 1)
            st.rerun()
        st.write(f"Page {current_page+1} of {total_pages}")
        selected_ids = []
        for msg in msgs:
            cols = st.columns([0.1, 0.9])
            with cols[0]:
                if st.checkbox("", key=f"chk_{msg.id}"):
                    selected_ids.append(msg.id)
            with cols[1]:
                st.markdown(f"**ID:** {msg.id} **From:** {msg.sender}")
                st.markdown(f"{msg.content}")
            st.markdown("---")
        if st.button("Delete Selected"):
            if not selected_ids:
                st.warning("Select messages to delete.")
            else:
                del_resp = self.client.delete_messages(st.session_state.auth_token, selected_ids)
                if not del_resp:
                    st.error("No response from server.")
                    return
                if del_resp.status == "ok":
                    st.success(f"Deleted {len(selected_ids)} messages.")
                    st.rerun()
                else:
                    st.error("Deletion failed.")

    def show_list_accounts_page(self):
        st.header("List Accounts")
        if "account_page" not in st.session_state:
            st.session_state.account_page = 0
        pattern = st.text_input("Username Pattern (use '*' for all)", "")
        accounts_per_page = st.number_input("Accounts per page", min_value=1, max_value=50, value=10, step=1)
        if st.button("Search / Refresh"):
            st.session_state.account_page = 0
        if pattern == "*":
            pattern = "%"
        if not pattern:
            st.info("Enter a pattern and click 'Search / Refresh'.")
            return
        total_resp = self.client.list_accounts(st.session_state.auth_token, pattern, 0, 1000)
        if not total_resp or total_resp.status != "ok":
            st.error(f"Error listing accounts: {total_resp.msg if total_resp else 'No response'}")
            return
        total_accounts = len(total_resp.users)
        if total_accounts == 0:
            st.warning("No accounts found.")
            return
        current_page = st.session_state.account_page
        start_offset = current_page * accounts_per_page
        page_resp = self.client.list_accounts(st.session_state.auth_token, pattern, start_offset, accounts_per_page)
        if not page_resp or page_resp.status != "ok":
            st.error(f"Error listing accounts: {page_resp.msg if page_resp else 'No response'}")
            return
        st.markdown("### Accounts on this page:")
        for user in page_resp.users:
            st.write(f"- {user.username}")
        total_pages = (total_accounts + accounts_per_page - 1) // accounts_per_page
        st.write(f"Page {current_page+1} of {total_pages}")
        cols = st.columns(2)
        with cols[0]:
            if current_page > 0:
                if st.button("Prev Accounts"):
                    st.session_state.account_page -= 1
                    st.rerun()
        with cols[1]:
            if current_page < total_pages - 1:
                if st.button("Next Accounts"):
                    st.session_state.account_page += 1
                    st.rerun()

    def show_delete_account_page(self):
        st.header("Delete Account")
        st.warning("This will delete your account permanently!")
        if st.button("Confirm Delete"):
            resp = self.client.delete_account(st.session_state.auth_token)
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.success("Account deleted.")
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.rerun()
            else:
                st.error("Deletion failed.")

    def show_logout_page(self):
        if st.button("Logout"):
            resp = self.client.logout(st.session_state.auth_token)
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.success("Logged out.")
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.rerun()
            else:
                st.error("Logout failed.")

    def run_app(self):
        self.apply_custom_css()
        st.title("JoChat - Automatic Failover with Server List")
        self.show_server_list()
        if st.session_state.logged_in:
            st.sidebar.markdown(f"**User:** {st.session_state.username}")
            menu = st.sidebar.radio("Navigation", ["Home", "Send Message", "Inbox", "List Accounts", "Delete Account", "Logout"])
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JoChat Client (Automatic Failover with Server List)")
    parser.add_argument("--servers", type=str, default="127.0.0.1:50051,127.0.0.1:50052,127.0.0.1:50053",
                        help="Comma-separated list of server addresses")
    args = parser.parse_args()
    server_list = [s.strip() for s in args.servers.split(",") if s.strip()]
    app = StreamlitChatApp(server_list)
    app.run_app()