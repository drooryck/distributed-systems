import grpc
import time
import threading
from concurrent import futures
from multiprocessing import Manager
import secrets
import argparse
import sys, os

# Make sure this import path is correct for your environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

# You have your own database.py with a Database class
from database import Database

HEARTBEAT_INTERVAL_SECS = 2.0
LEADER_TIMEOUT_SECS     = 6.0  # If we don't hear from the leader for this many seconds, we attempt election

class ChatServiceServicer(chat_service_pb2_grpc.ChatServiceServicer):
    def __init__(self, db, logged_in_users, server_id, port, peers):
        """
        :param db: Database instance
        :param logged_in_users: Manager dict for {auth_token -> username}
        :param server_id: unique integer ID for this server
        :param peers: list of (peer_id, peer_address) for all servers in the cluster (including self)
        """
        self.db = db
        self.logged_in_users = logged_in_users
        self.server_id = server_id
        self.my_addr = f"127.0.0.1:{port}"


        # Dictionary: peer_id -> peer_address
        self.peers = {server_id: self.my_addr}
        for pid, addr in peers:
            self.peers[pid] = addr
        print(self.peers)

        self.last_alive_peers = {}

        # For leader election
        # This node starts as a follower, not a leader
        self.is_leader = False
        self.current_leader_id = None
        self.last_leader_heartbeat = time.time()
        # If we are the smallest ID, we can become leader at startup if no existing leader is known
        # but let's let the heartbeat thread handle that after a small delay.

        # Start background thread to manage heartbeats & leader detection
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_manager, daemon=True)
        self.heartbeat_thread.start()

    def _heartbeat_manager(self):
        """
        Runs in a background thread. Responsible for:
         - If I'm leader, send heartbeats to all peers
         - If I'm not leader, watch for missed heartbeats
         - If leader is missed, do "lowest ID" election
        """
        while True:
            time.sleep(HEARTBEAT_INTERVAL_SECS)
            if self.is_leader:
                # Send a heartbeat to every other server
                for pid, paddr in self.peers.items():
                    if pid == self.server_id:
                        continue  # skip ourselves
                    try:
                        channel = grpc.insecure_channel(paddr)
                        stub = chat_service_pb2_grpc.ChatServiceStub(channel)
                        req = chat_service_pb2.HeartbeatRequest(
                            leader_id=self.server_id,
                            server_id=self.server_id
                        )
                        print(f"[Server {self.server_id}] Sending heartbeat to {pid} with leader_id={self.server_id}")

                        stub.Heartbeat(req, timeout=1.0)
                    except:
                        # peer might be down or unreachable; ignore for now
                        print('[Server {self.server_id}] Failed to send heartbeat to {pid}. Peer may be down or unreachable.')
                        pass
            else:
                # I'm not leader. Check if I have heard from the current leader recently.
                # If it's been more than LEADER_TIMEOUT_SECS, I trigger an election.
                now = time.time()
                #print(self.last_leader_heartbeat)
                if (now - self.last_leader_heartbeat) > LEADER_TIMEOUT_SECS:
                    print('x')
                    # The leader is presumably down or we've lost contact. Attempt election.
                    self._attempt_election()

    def _attempt_election(self):
        # Build a local dict of alive peers
        alive_peers = {self.server_id: self.peers.get(self.server_id, self.my_addr)}
        for pid, paddr in self.peers.items():
            if pid == self.server_id:
                continue
            try:
                channel = grpc.insecure_channel(paddr)
                stub = chat_service_pb2_grpc.ChatServiceStub(channel)
                req = chat_service_pb2.HeartbeatRequest(leader_id=-1, server_id=self.server_id)
                resp = stub.Heartbeat(req, timeout=1.0)
                # If we got here, it's alive
                alive_peers[pid] = paddr
            except:
                pass

        self.last_alive_peers = alive_peers

        # caused us a big headache
        # Do *not* overwrite self.peers here! We just use alive_peers for the election.
        min_alive_id = min(alive_peers.keys())

        if min_alive_id == self.server_id:
            self.is_leader = True
            self.current_leader_id = self.server_id
            print(f"[Server {self.server_id}] *** I am now the leader ***")
        else:
            self.is_leader = False
            self.current_leader_id = min_alive_id
            print(f"[Server {self.server_id}] New leader is {min_alive_id}")


    # ----------------------------------------------------
    # Heartbeat RPC
    # ----------------------------------------------------
    def Heartbeat(self, request, context):
        """
        Called by the leader or some node. We interpret if the 'leader_id' is valid or not.
        If request.leader_id == request.server_id, that node claims to be the leader.
        We record the heartbeat time if that is "better" or consistent with what we have.
        """
        claimed_leader = request.leader_id
        sender_id = request.server_id

        print(f"[Server {self.server_id}] Received heartbeat from {sender_id}, claimed leader: {claimed_leader}")


        # If the sender claims to be leader, we treat them as the leader
        if claimed_leader == sender_id and claimed_leader > 0:
            # Update local knowledge
            if self.current_leader_id != claimed_leader:
                print(f"[Server {self.server_id}] Detected new leader: {claimed_leader}")
                self.current_leader_id = claimed_leader

            self.last_leader_heartbeat = time.time()
            # If I thought I was the leader but apparently there's a smaller ID out there,
            # I'd relinquish. But in this simplest approach, we just trust "lowest ID" logic.
            if self.server_id != claimed_leader and self.is_leader:
                self.is_leader = False
                print(f"[Server {self.server_id}] im not the leader, new leader is {claimed_leader}")
        else:
            # It's just some follower or meaningless call.
            # That still updates last_leader_heartbeat if they gave a valid claimed_leader
            # (But often claimed_leader might be -1 if they're just testing connectivity)
            if claimed_leader > 0:
                self.current_leader_id = claimed_leader
                self.last_leader_heartbeat = time.time()

        return chat_service_pb2.HeartbeatResponse(
            status="ok",
            msg=f"Received heartbeat from server {sender_id}, leader = {claimed_leader}",
            current_leader_id=(self.current_leader_id if self.current_leader_id else -1)
        )

    # ----------------------------------------------------
    # Helper to replicate to all peers if I'm the leader
    # ----------------------------------------------------
    def replicate_to_peers(self, op_type, **kwargs):
        if not self.is_leader:
            return  # only the leader replicates
        for pid, paddr in self.peers.items():
            if pid == self.server_id:
                continue  # skip self
            try:
                channel = grpc.insecure_channel(paddr)
                stub = chat_service_pb2_grpc.ChatServiceStub(channel)
                req = chat_service_pb2.ReplicationRequest(op_type=op_type)
                if "sender" in kwargs:
                    req.sender = kwargs["sender"]
                if "recipient" in kwargs:
                    req.recipient = kwargs["recipient"]
                if "content" in kwargs:
                    req.content = kwargs["content"]
                if "message_ids" in kwargs:
                    req.message_ids.extend(kwargs["message_ids"])
                if "auth_token" in kwargs:
                    req.auth_token = kwargs["auth_token"]

                stub.Replicate(req, timeout=2.0)
            except Exception as e:
                print(f"[Server {self.server_id}] Failed to replicate {op_type} to {paddr}: {e}")

    # ----------------------------------------------------
    # Replicate RPC - if we are a follower, we just do the operation locally
    # ----------------------------------------------------
    def Replicate(self, request, context):
        op_type = request.op_type

        if op_type == "INSERT_MESSAGE":
            self.db.execute(
                """INSERT INTO messages (sender, recipient, content, to_deliver)
                   VALUES (?, ?, ?, ?)""",
                (request.sender, request.recipient, request.content, 1),
                commit=True
            )
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated insert")

        elif op_type == "DELETE_MESSAGES":
            placeholders = ",".join(["?" for _ in request.message_ids])
            self.db.execute(
                f"DELETE FROM messages WHERE id IN ({placeholders})",
                tuple(request.message_ids),
                commit=True
            )
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated delete")

        elif op_type == "SIGNUP_USER":
            row = self.db.execute("SELECT id FROM users WHERE username=?", (request.sender,), commit=True)
            if not row:
                self.db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (request.sender, request.content),
                    commit=True
                )
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated signup")

        elif op_type == "DELETE_ACCOUNT":
            user_to_del = request.sender
            self.db.execute("DELETE FROM messages WHERE sender=? OR recipient=?", (user_to_del, user_to_del), commit=True)
            self.db.execute("DELETE FROM users WHERE username=?",(user_to_del,), commit=True)
            self.db.execute("DELETE FROM sessions WHERE username=?", (user_to_del,), commit=True)

            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated account delete")

        elif op_type == "CREATE_SESSION":
            self.db.execute(
                "INSERT OR REPLACE INTO sessions (auth_token, username) VALUES (?, ?)",
                (request.auth_token, request.sender),
                commit=True
            )
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated session creation")
            
        elif op_type == "MARK_DELIVERED":
            if request.message_ids:
                placeholders = ",".join(["?"] * len(request.message_ids))
                self.db.execute(
                    f"UPDATE messages SET to_deliver=1 WHERE id IN ({placeholders})",
                    tuple(request.message_ids),
                    commit=True
                )
            return chat_service_pb2.GenericResponse(status="ok", msg="Marked messages delivered")

        elif op_type == "RESET_DB":
            # Drop tables and recreate them
            self.db.execute("DROP TABLE IF EXISTS users", commit=True)
            self.db.execute("DROP TABLE IF EXISTS messages", commit=True)
            self.db.execute("DROP TABLE IF EXISTS sessions", commit=True)  # If you want to remove sessions too
            self.db._init_db()
            return chat_service_pb2.GenericResponse(status="ok", msg="Replicated DB reset")



        return chat_service_pb2.GenericResponse(status="error", msg="Unknown replication op_type")

    # ----------------------------------------------------
    # RPC Implementations
    # ----------------------------------------------------
    def Signup(self, request, context):
        if not self.is_leader:
            return chat_service_pb2.GenericResponse(status="error", msg="NOT_LEADER")

        username, password = request.username, request.password
        if not username or not password:
            return chat_service_pb2.GenericResponse(status="error", msg="Username/password required")

        # Check if the username exists
        result = self.db.execute("SELECT id FROM users WHERE username=?", (username,), commit=True)
        if result:
            return chat_service_pb2.GenericResponse(status="error", msg="Username already taken")

        self.db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password), commit=True)
        self.replicate_to_peers("SIGNUP_USER", sender=username, content=password)

        return chat_service_pb2.GenericResponse(status="ok", msg="Signup successful")

    def Login(self, request, context):
        if not self.is_leader:
            return chat_service_pb2.LoginResponse(status="error", msg="NOT_LEADER")
        
        username, password = request.username, request.password
        if not username or not password:
            return chat_service_pb2.LoginResponse(status="error", msg="Username/password required")

        # If user is already logged in, forcibly log them out so they can re-login
            # for tok, logged_in_username in list(self.logged_in_users.items()):
            #     if logged_in_username == username:
            #         del self.logged_in_users[tok]
        # Invalidate any existing sessions for this user (log them out everywhere)
        self.db.execute("DELETE FROM sessions WHERE username=?", (username,), commit=True)


        row = self.db.execute("SELECT password_hash FROM users WHERE username=?", (username,), commit=True)
        if not row:
            return chat_service_pb2.LoginResponse(status="error", msg="Username not found")
        stored_hash = row[0][0]
        if stored_hash != password:
            return chat_service_pb2.LoginResponse(status="error", msg="Incorrect password")

        auth_token = secrets.token_hex(16)
        #self.logged_in_users[auth_token] = username
        self.db.execute("INSERT INTO sessions (auth_token, username) VALUES (?, ?)", (auth_token, username), commit=True)
        self.replicate_to_peers("CREATE_SESSION", auth_token=auth_token, sender=username)

        # unread count
        rows = self.db.execute(
            "SELECT COUNT(*) FROM messages WHERE recipient=? AND to_deliver=0",
            (username,),
            commit=True
        )
        unread_count = rows[0][0] if rows else 0

        return chat_service_pb2.LoginResponse(
            status="ok",
            msg="Login successful",
            auth_token=auth_token,
            unread_count=unread_count
        )


    def Logout(self, request, context):
        if not self.is_leader:
            return chat_service_pb2.GenericResponse(status="error", msg="NOT_LEADER")
        
        # First check if the session exists
        row = self.db.execute("SELECT username FROM sessions WHERE auth_token=?", (request.auth_token,), commit=False)
        
        if not row:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
        
        # Then delete the session
        self.db.execute("DELETE FROM sessions WHERE auth_token=?", (request.auth_token,), commit=True)
        
        # Replicate to peers
        self.replicate_to_peers("DELETE_SESSION", auth_token=request.auth_token)

        return chat_service_pb2.GenericResponse(status="ok", msg="You have been logged out.")

    def CountUnread(self, request, context):
        # select in the sessions table the username associated with the auth token
        row = self.db.execute("SELECT username FROM sessions WHERE auth_token=?", (request.auth_token,), commit=True)
        if not row:
            return chat_service_pb2.CountUnreadResponse(status="error", msg="Not logged in", unread_count=0)
        
        username = row[0][0]
        # could do one more failure handle here

        result = self.db.execute("SELECT COUNT(*) FROM messages WHERE recipient=? AND to_deliver=0", (username,), commit=True)
        unread_count = result[0][0] if result else 0
        return chat_service_pb2.CountUnreadResponse(status="ok", msg="Unread count fetched", unread_count=unread_count)

    def SendMessage(self, request, context):
        if not self.is_leader:
            return chat_service_pb2.GenericResponse(status="error", msg="NOT_LEADER")

        content, auth_token = request.content, request.auth_token
        # Get sender from sessions table
        row = self.db.execute("SELECT username FROM sessions WHERE auth_token=?", (auth_token,), commit=True)
        if not row:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")
        
        sender = row[0][0]

        row = self.db.execute("SELECT username FROM users WHERE username=?", (request.recipient,), commit=True)
        if not row:
            return chat_service_pb2.GenericResponse(status="error", msg="Recipient not found")
        recipient = row[0][0]
        row = self.db.execute("SELECT username FROM sessions WHERE username=?", (request.recipient,), commit=True)
        delivered_value = 1 if row else 0


        self.db.execute( "INSERT INTO messages (sender, recipient, content, to_deliver) VALUES (?, ?, ?, ?)", (sender, recipient, content, delivered_value), commit=True)

        self.replicate_to_peers("INSERT_MESSAGE", sender=sender, recipient=recipient, content=content)

        return chat_service_pb2.GenericResponse(status="ok", msg="Message sent")

    def ListMessages(self, request, context):
        # We allow ListMessages from any node
        # Validate session
        row = self.db.execute(
            "SELECT username FROM sessions WHERE auth_token=?",
            (request.auth_token,),
            commit=True
        )
        if not row:
            return chat_service_pb2.ListMessagesResponse(
                status="error",
                msg="Not logged in",
                messages=[],
                total_count=0
            )

        username = row[0][0]

        # total count
        row = self.db.execute("SELECT COUNT(*) FROM messages WHERE recipient=?", (username,))
        total_count = row[0][0] if row else 0

        # fetch the slice
        rows = self.db.execute("""
            SELECT id, sender, content, to_deliver
            FROM messages
            WHERE recipient=?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (username, request.count, request.start))

        messages = []
        for msg_id, sender, content, to_deliver in rows:
            cm = chat_service_pb2.ChatMessage(id=msg_id, sender=sender, content=content)
            messages.append(cm)

        return chat_service_pb2.ListMessagesResponse(
            status="ok",
            msg="Messages retrieved successfully",
            messages=messages,
            total_count=total_count
        )

    def FetchAwayMsgs(self, request, context):
        # Return them as a ListMessagesResponse for consistency
        # allowed only by leader
        if not self.is_leader:
            return chat_service_pb2.ListMessagesResponse(status="error", msg="NOT_LEADER", messages=[])
        
        # Validate session
        row = self.db.execute(
            "SELECT username FROM sessions WHERE auth_token=?",
            (request.auth_token,),
            commit=True
        )
        if not row:
            return chat_service_pb2.ListMessagesResponse(
                status="error",
                msg="Not logged in",
                messages=[]
            )
        
        username = row[0][0]
        rows = self.db.execute("""
            SELECT id, sender, content
            FROM messages
            WHERE recipient=? AND to_deliver=0
            ORDER BY id ASC
            LIMIT ?
        """, (username, request.limit), commit=True)

        # Mark them delivered
        if rows:
            msg_ids = [r[0] for r in rows]
            placeholders = ",".join(["?" for _ in msg_ids])
            self.db.execute(
                f"UPDATE messages SET to_deliver=1 WHERE id IN ({placeholders})",
                tuple(msg_ids),
                commit=True
            )

            self.replicate_to_peers("MARK_DELIVERED", message_ids=msg_ids)

        messages = [
            chat_service_pb2.ChatMessage(id=r[0], sender=r[1], content=r[2]) for r in rows
        ]

        return chat_service_pb2.ListMessagesResponse(
            status="ok",
            msg="Messages retrieved successfully",
            messages=messages
        )

    def ListAccounts(self, request, context):
        # 1) Check if auth token is valid via the sessions table
        row = self.db.execute(
            "SELECT username FROM sessions WHERE auth_token=?",
            (request.auth_token,),
            commit=True
        )
        if not row:
            return chat_service_pb2.ListAccountsResponse(
                status="error",
                msg="Not logged in",
                users=[]
            )

        # 2) Pattern logic (unchanged)
        pattern = request.pattern.strip()
        if pattern == "*":
            pattern = "%"
        elif pattern and not pattern.startswith("%"):
            pattern = f"%{pattern}%"

        rows = self.db.execute(
            "SELECT id, username FROM users WHERE username LIKE ? LIMIT ? OFFSET ?",
            (pattern, request.count, request.start),
            commit=True
        )

        # 3) Build the response
        users = []
        for r in rows:
            users.append(chat_service_pb2.UserRecord(id=r[0], username=r[1]))

        return chat_service_pb2.ListAccountsResponse(
            status="ok",
            msg="Accounts retrieved successfully",
            users=users
        )


    def DeleteMessages(self, request, context):
        if not self.is_leader:
            return chat_service_pb2.DeleteMessagesResponse(status="error", msg="NOT_LEADER", deleted_count=0)
        
        # 2) Validate session
        row = self.db.execute("SELECT username FROM sessions WHERE auth_token=?", (request.auth_token,), commit=True)
        if not row:
            return chat_service_pb2.DeleteMessagesResponse(status="error", msg="Not logged in", deleted_count=0)

        username = row[0][0]
        msg_ids = list(request.message_ids_to_delete)

        placeholders = ",".join(["?"] * len(msg_ids))
        params = [username] + msg_ids
        self.db.execute(f"DELETE FROM messages WHERE recipient=? AND id IN ({placeholders})", params, commit=True)
        self.replicate_to_peers("DELETE_MESSAGES", message_ids=msg_ids)

        return chat_service_pb2.DeleteMessagesResponse(status="ok", msg="Messages deleted successfully", deleted_count=len(msg_ids))

    def DeleteAccount(self, request, context):
        if not self.is_leader:
            return chat_service_pb2.GenericResponse(status="error", msg="NOT_LEADER")
        
        # 2) Validate session
        row = self.db.execute("SELECT username FROM sessions WHERE auth_token=?", (request.auth_token,), commit=True)
        if not row:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")

        username = row[0][0]

        self.db.execute("DELETE FROM messages WHERE sender=? OR recipient=?", (username, username), commit=True)
        self.db.execute("DELETE FROM users WHERE username=?", (username,), commit=True)
        self.db.execute("DELETE FROM sessions WHERE username=?", (username,), commit=True)


        self.replicate_to_peers("DELETE_ACCOUNT", sender=username)
        # replicate other changes.
        return chat_service_pb2.GenericResponse(status="ok", msg="Account deleted successfully")

    def ResetDB(self, request, context):
        # 1) Must be leader
        if not self.is_leader:
            return chat_service_pb2.GenericResponse( status="error", msg="NOT_LEADER" )

        # 2) Validate session
        row = self.db.execute("SELECT username FROM sessions WHERE auth_token=?", (request.auth_token,), commit=True)
        if not row:
            return chat_service_pb2.GenericResponse(status="error", msg="Not logged in")

        # 3) Drop tables & re-init
        self.db.execute("DROP TABLE IF EXISTS users", commit=True)
        self.db.execute("DROP TABLE IF EXISTS messages", commit=True)
        self.db.execute("DROP TABLE IF EXISTS sessions", commit=True)
        self.db._init_db()

        # (Optional) replicate if you want all nodes to do it
        self.replicate_to_peers("RESET_DB")

        return chat_service_pb2.GenericResponse(status="ok", msg="Database reset successfully")
    
    def ClusterInfo(self, request, context):
        # Must be leader
        if not self.is_leader:
            return chat_service_pb2.ClusterInfoResponse(
                status="error",
                msg="NOT_LEADER",
                servers=[]
            )

        # Validate session
        row = self.db.execute(
            "SELECT username FROM sessions WHERE auth_token=?",
            (request.auth_token,),
            commit=True
        )
        if not row:
            return chat_service_pb2.ClusterInfoResponse(
                status="error",
                msg="Not logged in",
                servers=[]
            )

        # Build list of known-alive peers from last election
        servers = []
        for sid, addr in self.last_alive_peers.items():
            sinfo = chat_service_pb2.ServerInfo(server_id=sid, address=addr)
            servers.append(sinfo)

        return chat_service_pb2.ClusterInfoResponse(
            status="ok",
            msg=f"Current leader is {self.current_leader_id}",
            servers=servers
        )


def serve():
    parser = argparse.ArgumentParser(description="Chat Server (with leader election & replication)")
    parser.add_argument("--server_id", type=int, required=True, help="Unique integer ID for this server")
    parser.add_argument("--port", type=int, default=50051, help="Port to listen on")
    parser.add_argument("--db_file", type=str, default="chat.db", help="SQLite DB file name")
    parser.add_argument("--peers", type=str, default="", help="Comma-separated list of peer definitions, e.g. '1:127.0.0.1:50051,2:127.0.0.1:50052'")
    args = parser.parse_args()
    

    # Parse peers
    # Expects something like "1:127.0.0.1:50051,2:127.0.0.1:50052,3:127.0.0.1:50053"
    # We'll store them as a list of (id, address)
    peers = []
    if args.peers.strip():
        for chunk in args.peers.split(","):
            chunk = chunk.strip()
            # "1:127.0.0.1:50051"
            sid_str, address = chunk.split(":", 1)
            sid = int(sid_str)
            peers.append((sid, address))

    db = Database(args.db_file)
    # We use Manager dict for concurrency
    logged_in_users = Manager().dict()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = ChatServiceServicer(db, logged_in_users, args.server_id, args.port, peers)
    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(servicer, server)

    listen_addr = f"[::]:{args.port}"
    server.add_insecure_port(listen_addr)
    print(f"Starting server {args.server_id} on port {args.port} with DB={args.db_file}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
