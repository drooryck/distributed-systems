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

    MANUAL FAILOVER version:
      - We store multiple server addresses, but only connect to ONE at a time.
      - The user can pick which address is the "active" server in the Streamlit UI.
    """

    def __init__(self, server_addresses):
        """
        server_addresses: list of possible gRPC addresses (e.g. ["127.0.0.1:50051", "127.0.0.1:50052"]).
        We will default to the first one, but user can switch manually in the UI.
        """
        self.server_addresses = server_addresses
        # Start with the first address, or none if empty
        self.active_address = server_addresses[0] if server_addresses else None
        self.stub = None
        self.connect_stub()

    def connect_stub(self):
        """(Re)connects the gRPC stub for the currently active address."""
        if not self.active_address:
            st.warning("No active server address set!")
            self.stub = None
            return
        channel = grpc.insecure_channel(self.active_address)
        self.stub = chat_service_pb2_grpc.ChatServiceStub(channel)

    def set_active_address(self, addr):
        """Switch to a new server address, and re-create the stub."""
        self.active_address = addr
        self.connect_stub()

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

###############################################################################
# StreamlitChatApp
###############################################################################
class StreamlitChatApp:
    """
    Main application class for our Streamlit-based Chat App, 
    with MANUAL FAILOVER to survive up to 2 crashes (the user picks which server is up).
    
    Data in st.session_state includes:
      - logged_in, username, inbox_page, auth_token, account_page, active_server
    """

    def __init__(self, server_addresses):
        self.server_addresses = server_addresses
        self._init_session_state()
        # Build a ChatServerClient that starts on whichever address is in session_state.active_server
        self.client = None
        self._ensure_client()

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
        # For manual failover, store which server is currently active
        if "active_server" not in st.session_state:
            # Default to the first server in the list
            st.session_state.active_server = self.server_addresses[0] if self.server_addresses else None

    def _ensure_client(self):
        """Ensure self.client is set up with the correct active address from session_state."""
        if not st.session_state.active_server:
            st.warning("No server addresses provided or no active_server set.")
            return
        if not self.client:
            # Build a new ChatServerClient
            self.client = ChatServerClient(self.server_addresses)
        # If the stored active_server differs from the client's active_address, update it:
        if self.client.active_address != st.session_state.active_server:
            self.client.set_active_address(st.session_state.active_server)

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
    # Helpers to get "stub" from the active client
    ###########################################################################
    @property
    def stub(self):
        if self.client:
            return self.client.stub
        return None

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
                if not self.stub:
                    st.error("No gRPC stub available (server offline?).")
                    return
                resp = self.stub.Login(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))
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
                    st.error(str(resp.status))

            else:  # "Create Account"
                if not self.stub:
                    st.error("No gRPC stub available (server offline?).")
                    return
                signup_resp = self.stub.Signup(chat_service_pb2.SignupRequest(username=username, password=hashed_pw))
                if not signup_resp:
                    st.error("No response from server.")
                    return
                if signup_resp.status != "ok":
                    st.error(signup_resp.msg if signup_resp.msg else "Account creation failed.")
                    return
                # Auto-login
                login_resp = self.stub.Login(chat_service_pb2.LoginRequest(username=username, password=hashed_pw))
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
        if not self.stub:
            st.error("No gRPC stub available (server offline?).")
            return
        resp = self.stub.CountUnread(chat_service_pb2.CountUnreadRequest(auth_token=st.session_state.auth_token))
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
            if not self.stub:
                st.error("No gRPC stub available (server offline?).")
                return
            resp = self.stub.SendMessage(
                chat_service_pb2.SendMessageRequest(
                    auth_token=st.session_state.auth_token, 
                    recipient=recipient, 
                    content=message_text
                )
            )
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

        # (A) Manual Fetch for Offline Messages
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
            if not self.stub:
                st.error("No gRPC stub available (server offline?).")
                return
            away_resp = self.stub.FetchAwayMsgs(
                chat_service_pb2.FetchAwayMsgsRequest(
                    limit=manual_fetch_count,
                    auth_token=st.session_state.auth_token
                )
            )
            if not away_resp:
                st.error("No response from server.")
                return
            if away_resp.status == "ok":
                st.rerun()
            else:
                st.error("Manual fetch failed or returned an error.")

        # B) Pagination
        if "inbox_page" not in st.session_state:
            st.session_state.inbox_page = 0
        MESSAGES_PER_PAGE = 10
        current_page = st.session_state.inbox_page
        start_offset = current_page * MESSAGES_PER_PAGE

        if not self.stub:
            st.error("No gRPC stub available (server offline?).")
            return
        list_resp = self.stub.ListMessages(
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
        ### SHOW THE MESSAGES
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

        if st.button("Delete Selected"):
            if not selected_msg_ids:
                st.warning("No messages selected for deletion.")
            else:
                if not self.stub:
                    st.error("No gRPC stub available (server offline?).")
                    return
                del_resp = self.stub.DeleteMessages(
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

        if not self.stub:
            st.error("No gRPC stub available (server offline?).")
            return
        

        # 4) First, fetch total number of matching accounts
        #    by requesting a large count (or you could define a dedicated Count API).
        total_resp = self.stub.ListAccounts(
            chat_service_pb2.ListAccountsRequest(
                auth_token=st.session_state.auth_token,
                pattern=pattern,
                start=0,
                count=1000
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
        current_page = st.session_state.account_page
        start_offset = current_page * accounts_per_page

        page_resp = self.stub.ListAccounts(
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
            if not self.stub:
                st.error("No gRPC stub available (server offline?).")
                return
            resp = self.stub.DeleteAccount(chat_service_pb2.EmptyRequest(auth_token=st.session_state.auth_token))
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
            if not self.stub:
                st.error("No gRPC stub available (server offline?).")
                return
            resp = self.stub.Logout(chat_service_pb2.EmptyRequest(auth_token=st.session_state.auth_token))
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
    # Manual Failover Controls
    ###########################################################################
    def show_failover_controls(self):
        """
        Allows the user to manually select which server is "active."
        This is how we handle manual failover (simply pick the server that is still up).
        """
        st.sidebar.markdown("### MANUAL FAILOVER CONTROLS")
        if not self.server_addresses:
            st.sidebar.warning("No server addresses configured.")
            return
        selected = st.sidebar.selectbox(
            "Select Active Server",
            self.server_addresses,
            index=self.server_addresses.index(st.session_state.active_server) 
            if st.session_state.active_server in self.server_addresses else 0
        )
        if selected != st.session_state.active_server:
            st.session_state.active_server = selected
            self._ensure_client()
            st.rerun()

    ###########################################################################
    # Main run_app
    ###########################################################################
    def run_app(self):
        self.apply_custom_css()
        st.title("JoChat (Manual Failover Version)")

        # Show sidebar failover controls
        self.show_failover_controls()

        # Now show normal UI
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
    parser = argparse.ArgumentParser(description="JoChat Client (Manual Failover)")
    parser.add_argument("--servers", type=str, default="127.0.0.1:50051",
                        help="Comma-separated list of possible servers (e.g. '127.0.0.1:50051,127.0.0.1:50052')")
    args = parser.parse_args()

    server_list = [s.strip() for s in args.servers.split(",") if s.strip()]
    if not server_list:
        print("No server addresses provided. Exiting.")
        sys.exit(1)

    app = StreamlitChatApp(server_list)
    app.run_app()
