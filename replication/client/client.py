#!/usr/bin/env python3
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import hashlib
import argparse
import sys, os
import grpc
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

###############################################################################
# ChatServerClient (Automatic Failover with a list of servers)
###############################################################################
class ChatServerClient:
    """
    This client stores a list of server addresses and attempts automatic failover.
    It tries the current server; if the RPC call fails or the server says "NOT_LEADER",
    it cycles through the list.
    """
    def __init__(self, server_addresses):
        if not server_addresses:
            raise ValueError("No server addresses provided.")
        self.server_addresses = server_addresses
        self.current_idx = 0
        self.last_update_time = 0
        self.ttl = 10  # seconds

    def _try_stub_call(self, rpc_name, request):
        now = time.time()
        if now - self.last_update_time > self.ttl:
            self._refresh_server_list(request)
        num_servers = len(self.server_addresses)
        attempts = 0
        while attempts < num_servers:
            addr = self.server_addresses[self.current_idx]
            try:
                channel = grpc.insecure_channel(addr)
                stub = chat_service_pb2_grpc.ChatServiceStub(channel)
                rpc_method = getattr(stub, rpc_name)
                response = rpc_method(request, timeout=2.0)

                if hasattr(response, "status") and response.status == "error" and response.msg == "NOT_LEADER":
                    raise grpc.RpcError("Server not leader")
                
                # CAN BE NICE TO HAVE IN DEBUG MODE
                # st.success(f"found leader, it is server {addr}")
                return response

            except grpc.RpcError as e:
                # MAY WANT TO INCLUDE 'e' for DEBUGGING PURPOSES.
                st.warning(f"Server {addr} failed or not leader:. Trying next.")
                self.current_idx = (self.current_idx + 1) % num_servers
                attempts += 1

        st.error("All servers are down or refusing writes.")
        return None

    def _refresh_server_list(self, request):
        for addr in self.server_addresses:
            try:
                channel = grpc.insecure_channel(addr)
                stub = chat_service_pb2_grpc.ChatServiceStub(channel)
                cluster_info = stub.ClusterInfo(request, timeout=2.0)
                if cluster_info.status == "ok":
                    updated = [s.address for s in cluster_info.servers if s.address not in self.server_addresses]
                    self.server_addresses.extend(updated)
                    self.last_update_time = time.time()
                    return
            except:
                continue

    def signup(self, username, password):
        req = chat_service_pb2.SignupRequest(username=username, password=password)
        return self._try_stub_call("Signup", req)

    def login(self, username, password):
        req = chat_service_pb2.LoginRequest(username=username, password=password)
        return self._try_stub_call("Login", req)

    def logout(self, auth_token):
        req = chat_service_pb2.EmptyRequest(auth_token=auth_token)
        return self._try_stub_call("Logout", req)

    def count_unread(self, auth_token):
        req = chat_service_pb2.CountUnreadRequest(auth_token=auth_token)
        return self._try_stub_call("CountUnread", req)

    def send_message(self, auth_token, recipient, content):
        req = chat_service_pb2.SendMessageRequest(auth_token=auth_token, recipient=recipient, content=content)
        return self._try_stub_call("SendMessage", req)

    def list_messages(self, auth_token, start, count):
        req = chat_service_pb2.ListMessagesRequest(auth_token=auth_token, start=start, count=count)
        return self._try_stub_call("ListMessages", req)

    def fetch_away_msgs(self, auth_token, limit):
        req = chat_service_pb2.FetchAwayMsgsRequest(auth_token=auth_token, limit=limit)
        return self._try_stub_call("FetchAwayMsgs", req)

    def list_accounts(self, auth_token, pattern, start, count):
        req = chat_service_pb2.ListAccountsRequest(auth_token=auth_token, pattern=pattern, start=start, count=count)
        return self._try_stub_call("ListAccounts", req)

    def delete_messages(self, auth_token, message_ids):
        req = chat_service_pb2.DeleteMessagesRequest(auth_token=auth_token, message_ids_to_delete=message_ids)
        return self._try_stub_call("DeleteMessages", req)

    def delete_account(self, auth_token):
        req = chat_service_pb2.EmptyRequest(auth_token=auth_token)
        return self._try_stub_call("DeleteAccount", req)
    
    def get_cluster_info(self, auth_token):
        req = chat_service_pb2.EmptyRequest(auth_token=auth_token)
        return self._try_stub_call("ClusterInfo", req)

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()



###############################################################################
# StreamlitChatApp (Automatic Failover with Client Persistence)
###############################################################################
class StreamlitChatApp:
    def __init__(self, server_addresses):
        self.server_addresses = server_addresses
        self._init_session_state()
        self._init_client()  # Persist the client across reruns

    def _init_session_state(self):
        # Persistent across pages
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

    def _init_client(self):
        # Only create the ChatServerClient once and persist it in session state.
        if "chat_client" not in st.session_state:
            st.session_state.chat_client = ChatServerClient(self.server_addresses)
        self.client = st.session_state.chat_client

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
                    st.error(str(resp.status) + ": " + resp.msg)
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
                st.success("Account created and logged in successfully!")
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.auth_token = login_resp.auth_token
                st.rerun()

    def show_home_page(self):
        st.header("Welcome!")
        resp = self.client.count_unread(st.session_state.auth_token)
        unread_count = resp.unread_count if (resp and resp.status == "ok") else 0
        st.write(f"You have {unread_count} unread message(s).")
        st.info("Use the sidebar to navigate to Send Message, Inbox, List Accounts, Delete Account, or Logout.")

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
                st.error(f"Message failed: {resp.msg}")

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
            resp = self.client.fetch_away_msgs(st.session_state.auth_token, manual_fetch_count)
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.rerun()
            else:
                st.error("Manual fetch failed or returned an error.")
        MESSAGES_PER_PAGE = 10
        current_page = st.session_state.inbox_page
        start_offset = current_page * MESSAGES_PER_PAGE
        list_resp = self.client.list_messages(st.session_state.auth_token, start_offset, MESSAGES_PER_PAGE)
        if not list_resp:
            st.error("No response from server.")
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
        st.write(f"**Page {current_page+1} of {total_pages}**")
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
        selected_ids = []
        for msg in msgs:
            cols = st.columns([0.1, 0.9])
            with cols[0]:
                if st.checkbox("selected", key=f"select_{msg.id}", label_visibility="collapsed"):
                    selected_ids.append(msg.id)
            with cols[1]:
                st.markdown(f"**ID:** {msg.id} | **From:** {msg.sender}")
                st.markdown(f"<div style='padding: 0.5rem 0;'>{msg.content}</div>", unsafe_allow_html=True)
            st.markdown("---")
        if st.button("Delete Selected"):
            if not selected_ids:
                st.warning("No messages selected for deletion.")
            else:
                del_resp = self.client.delete_messages(st.session_state.auth_token, selected_ids)
                if not del_resp:
                    st.error("No response from server.")
                    return
                if del_resp.status == "ok":
                    st.success(f"Deleted {len(selected_ids)} message(s).")
                    st.rerun()
                else:
                    st.error(f"Deletion of selected messages failed: {del_resp.msg}")

    def show_list_accounts_page(self):
        st.header("Search / List Accounts")
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
        all_users = total_resp.users
        total_accounts = len(all_users)
        if total_accounts == 0:
            st.warning("No accounts found matching your search criteria.")
            return
        current_page = st.session_state.account_page
        start_offset = current_page * accounts_per_page
        page_resp = self.client.list_accounts(
            st.session_state.auth_token, pattern, start_offset, accounts_per_page
        )
        if not page_resp or page_resp.status != "ok":
            st.error(f"Could not list accounts. Server status: {getattr(page_resp, 'status', 'no response')}")
            return
        page_users = page_resp.users
        st.markdown("**Matching Accounts (this page):**")
        for acc in page_users:
            st.write(f"- {acc.username}")
        total_pages = (total_accounts + accounts_per_page - 1) // accounts_per_page
        st.write(f"**Page {current_page+1} of {total_pages}**")
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

    def show_delete_account_page(self):
        st.header("Delete Account")
        st.warning("This will permanently delete your account and all associated messages!")
        if st.button("Confirm Delete Account"):
            resp = self.client.delete_account(st.session_state.auth_token)
            if not resp:
                st.error("No response from server.")
                return
            if resp.status == "ok":
                st.success("Account deleted successfully!")
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.rerun()
            else:
                st.error("Deletion of account failed.")

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
                st.error("Logout was refused by the server.")

    def show_cluster_info_page(self):
        st.header("Cluster Information")
        resp = self.client.get_cluster_info(auth_token=st.session_state.auth_token)
        if not resp:
            st.error("Failed to retrieve cluster information. All servers may be unreachable.")
            return
        
        if resp.status != "ok":
            st.error(f"Failed to retrieve cluster information: {resp.msg}")
            return
        
        # Show leader information
        if hasattr(resp, 'leader') and resp.leader.server_id != -1:
            st.write("### Leader server:")
            st.write(f"Server {resp.leader.server_id}: {resp.leader.address}")
        else:
            st.warning("No active leader found in the cluster")
        
        # Show alive servers
        if hasattr(resp, 'servers') and len(resp.servers) > 0:
            st.write("### Known servers:")
            for server in resp.servers:
                # Add a visual indicator for the leader
                is_leader = hasattr(resp, 'leader') and server.server_id == resp.leader.server_id
                leader_badge = "🔴 LEADER" if is_leader else ""
                st.write(f"Server {server.server_id}: {server.address} {leader_badge}")
        else:
            st.warning("No active servers found in the cluster")


    def run_app(self):
        self.apply_custom_css()
        st.title("JoChat (Leader-Election Edition)")
        if st.session_state.logged_in:
            st.sidebar.markdown(f"**User:** {st.session_state.username}")
            menu = st.sidebar.radio("Navigation", ["Home", "Send Message", "Inbox", "List Accounts", "Delete Account", "Logout", "Cluster Info"])
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
            elif menu == "Cluster Info":
                self.show_cluster_info_page()
        else:
            self.show_login_or_signup_page()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JoChat Client (Automatic Failover with Server List)")
    parser.add_argument("--servers", type=str, default="10.250.25.214:50051,10.250.25.214:50052,10.250.25.214:50053",
                        help="Comma-separated list of server addresses")
    args = parser.parse_args()

    server_list = [s.strip() for s in args.servers.split(",") if s.strip()]
    app = StreamlitChatApp(server_list)
    app.run_app()
