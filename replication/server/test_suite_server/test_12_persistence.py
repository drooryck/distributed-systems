import unittest
import subprocess
import time
import sqlite3
import os
import grpc
from test_base import BaseTest
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

# Helper to start a server process
def start_server(server_id, port, db_file, peers):
    cmd = [
        "python", "../server.py",
        f"--server_id={server_id}",
        f"--port={port}",
        f"--db_file={db_file}",
        f"--peers={peers}"
    ]
    return subprocess.Popen(cmd, stdout=None, stderr=None)

def query_db(db_file, query, params=()):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute(query, params)
    results = c.fetchall()
    conn.close()
    return results

class TestPersistence(BaseTest):
    """
    Persistence Test:
    Start all three servers, perform operations on the leader,
    then perform a planned shutdown (kill all servers) and restart them.
    Finally, verify that all messages (and user data) persist across restarts.
    """
    # Server configuration
    SERVERS = [
        {"server_id": 1, "port": 50051, "db_file": "test_chat1.db", "peers": "2:127.0.0.1:50052,3:127.0.0.1:50053"},
        {"server_id": 2, "port": 50052, "db_file": "test_chat2.db", "peers": "1:127.0.0.1:50051,3:127.0.0.1:50053"},
        {"server_id": 3, "port": 50053, "db_file": "test_chat3.db", "peers": "1:127.0.0.1:50051,2:127.0.0.1:50052"}
    ]
    
    def setUp(self):
        # Start all server processes without deleting the DB files.
        self.procs = []
        for s in self.SERVERS:
            proc = start_server(
                s["server_id"],
                s["port"],
                s["db_file"],
                s["peers"]
            )
            self.procs.append(proc)
        
        # Wait a few seconds for servers to start.
        time.sleep(3)
        
        # Connect to leader (assumed on port 50051) and reset DB.
        self.leader_channel = grpc.insecure_channel("localhost:50051")
        self.leader_stub = chat_service_pb2_grpc.ChatServiceStub(self.leader_channel)
        self.leader_stub.Signup(chat_service_pb2.SignupRequest(username="admin", password="adminpass"))
        admin_login = self.leader_stub.Login(chat_service_pb2.LoginRequest(username="admin", password="adminpass"))
        if admin_login.status != "ok":
            raise RuntimeError("Admin login failed; cannot reset DB")
        
        self.leader_stub.ResetDB(chat_service_pb2.EmptyRequest(auth_token=admin_login.auth_token))
        time.sleep(2)
        
    def tearDown(self):
        # Kill all server processes.
        for proc in self.procs:
            proc.terminate()
            proc.wait()
        self.leader_channel.close()
        
    def test_persistence_after_restart(self):
        # Step 1: Perform operations via the leader.
        signup_alice = self.leader_stub.Signup(
            chat_service_pb2.SignupRequest(
                username="Alice",
                password="secret"
            )
        )
        self.assertEqual(signup_alice.status, "ok", "Signup for Alice failed")
        
        signup_bob = self.leader_stub.Signup(
            chat_service_pb2.SignupRequest(
                username="Bob",
                password="passB"
            )
        )
        self.assertEqual(signup_bob.status, "ok", "Signup for Bob failed")
        
        login_alice = self.leader_stub.Login(
            chat_service_pb2.LoginRequest(
                username="Alice",
                password="secret"
            )
        )
        self.assertEqual(login_alice.status, "ok", "Login for Alice failed")
        
        token_alice = login_alice.auth_token
        send_response = self.leader_stub.SendMessage(
            chat_service_pb2.SendMessageRequest(
                auth_token=token_alice,
                recipient="Bob",
                content="Persistence test message"
            )
        )
        self.assertEqual(send_response.status, "ok", "Send message failed on leader")
        time.sleep(2)  # Ensure operations finish on the leader.
        
        # Step 2: Kill all servers (done in tearDown) and restart them.
        for proc in self.procs:
            proc.terminate()
            proc.wait()
        
        # Restart servers with the same DB files (no deletion).
        self.procs = []
        for s in self.SERVERS:
            proc = start_server(
                s["server_id"],
                s["port"],
                s["db_file"],
                s["peers"]
            )
            self.procs.append(proc)
        time.sleep(3)  # Give them time to come back up.
        
        # Step 3: Connect again to the leader (assume leader remains on port 50051).
        channel = grpc.insecure_channel("localhost:50051")
        stub = chat_service_pb2_grpc.ChatServiceStub(channel)
        
        # Verify that the message persists in each DB.
        for s in self.SERVERS:
            db_file = s["db_file"]
            self.assertTrue(os.path.exists(db_file), f"DB file {db_file} does not exist after restart")
            
            # Check that users exist (Alice and Bob).
            users = query_db(db_file, "SELECT username FROM users WHERE username IN (?, ?)", ("Alice", "Bob"))
            usernames = [row[0] for row in users]
            self.assertIn("Alice", usernames, f"Alice not found in {db_file}")
            self.assertIn("Bob", usernames, f"Bob not found in {db_file}")
            
            # Check that the message persists.
            messages = query_db(
                db_file,
                "SELECT sender, recipient, content FROM messages WHERE sender=? AND recipient=?",
                ("Alice", "Bob")
            )
            self.assertGreaterEqual(len(messages), 1, f"No message from Alice to Bob found in {db_file}")
            found = any("Persistence test message" in row[2] for row in messages)
            self.assertTrue(found, f"Expected message not found in {db_file}")
        
        channel.close()

if __name__ == "__main__":
    unittest.main()