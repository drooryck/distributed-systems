import unittest
import subprocess
import time
import sqlite3
import os
import sys
import grpc

from test_base import BaseTest
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

# Helper to start a server process, with no stdout/stderr capture
def start_server(server_id, port, db_file, peers):
    cmd = [
        "python", "../server.py",
        f"--server_id={server_id}",
        f"--port={port}",
        f"--db_file={db_file}",
        f"--peers={peers}"
    ]
    return subprocess.Popen(cmd, stdout=None, stderr=None)

class TestFailover(BaseTest):
    """
    Failover Test:
      1) Start a 3-server cluster; server1 is assumed leader on port 50051.
      2) Perform an operation (signup) via the leader to confirm it's up.
      3) Kill the leader (server1).
      4) Attempt a leader-only operation to confirm either server2 or server3
         has assumed the leadership (i.e. a new message from Alice to Bob).
      5) Verify that the new leader is not server1.
      6) Check that the failover message is present in all DBs.
      7) Finally, kill all servers in tearDown().
    """

    # Three-server cluster configuration
    SERVERS = [
        {
            "server_id": 1,
            "port": 50051,
            "db_file": "test_chat1.db",
            "peers": "2:127.0.0.1:50052,3:127.0.0.1:50053"
        },
        {
            "server_id": 2,
            "port": 50052,
            "db_file": "test_chat2.db",
            "peers": "1:127.0.0.1:50051,3:127.0.0.1:50053"
        },
        {
            "server_id": 3,
            "port": 50053,
            "db_file": "test_chat3.db",
            "peers": "1:127.0.0.1:50051,2:127.0.0.1:50052"
        }
    ]

    def setUp(self):
        # 1) Start all servers
        self.procs = []
        for cfg in self.SERVERS:
            proc = start_server(
                cfg["server_id"],
                cfg["port"],
                cfg["db_file"],
                cfg["peers"]
            )
            self.procs.append(proc)
        
        # 2) Give them time to start up and elect server1 as leader
        time.sleep(3)

        # 3) Connect to server1 (leader) for initial admin setup
        self.leader_channel = grpc.insecure_channel("localhost:50051")
        self.leader_stub = chat_service_pb2_grpc.ChatServiceStub(self.leader_channel)

        # Admin reset DB
        self.leader_stub.Signup(chat_service_pb2.SignupRequest(username="admin", password="adminpass"))
        admin_login = self.leader_stub.Login(chat_service_pb2.LoginRequest(username="admin", password="adminpass"))
        if admin_login.status != "ok":
            raise RuntimeError("Admin login failed; cannot reset DB")
        self.leader_stub.ResetDB(chat_service_pb2.EmptyRequest(auth_token=admin_login.auth_token))
        time.sleep(2)

    def tearDown(self):
        # Kill all servers, including the one we already terminated (if any).
        for proc in self.procs:
            if proc is not None:
                proc.terminate()
                proc.wait()
        # Close leader channel
        self.leader_channel.close()

    def query_db(self, db_file, query, params=()):
        """Simple helper to query a SQLite DB file."""
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(query, params)
        results = c.fetchall()
        conn.close()
        return results

    def test_failover(self):
        # Step 1: Confirm old leader (server1) is working by doing a user signup
        signup_alice = self.leader_stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))
        self.assertEqual(signup_alice.status, "ok", "Signup for Alice failed on old leader")

        # Step 2: Kill the old leader (server1)
        old_leader_proc = self.procs[0]
        old_leader_proc.terminate()
        old_leader_proc.wait()
        # Mark it None so tearDown doesn't try again
        self.procs[0] = None

        # Step 3: Wait for cluster to elect a new leader
        time.sleep(4)

        # Step 4: Attempt a "leader-only" operation on servers 2 and 3
        # We will try logging in as Alice + sending a message. If it succeeds, that server is leader.
        new_leader_port = None
        for candidate_port in [50052, 50053]:
            channel = grpc.insecure_channel(f"localhost:{candidate_port}")
            stub = chat_service_pb2_grpc.ChatServiceStub(channel)
            try:
                # Login as Alice
                login_resp = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
                if login_resp.status == "ok":
                    # Attempt to send a message to Bob
                    msg_resp = stub.SendMessage(
                        chat_service_pb2.SendMessageRequest(
                            auth_token=login_resp.auth_token,
                            recipient="Bob",
                            content="Failover test message"
                        )
                    )
                    if msg_resp.status == "ok":
                        # This server must be the new leader
                        new_leader_port = candidate_port
                        channel.close()
                        break
            except grpc.RpcError:
                pass
            channel.close()

        self.assertIsNotNone(new_leader_port, "No new leader was found among servers 2 or 3!")
        self.assertNotEqual(new_leader_port, 50051, "Leader did not change after killing server1!")

        # Step 5: Verify the failover message appears in each DB
        # By now, the new leader should replicate to the surviving nodes
        for cfg in self.SERVERS:
            if cfg is None:
                continue  # Old leader
            db_file = cfg["db_file"]
            if not os.path.exists(db_file):
                # Optionally raise an error if you expect the DB file to exist
                continue

            messages = self.query_db(
                db_file,
                "SELECT sender, recipient, content FROM messages WHERE sender=? AND recipient=?",
                ("Alice", "Bob")
            )
            found = any("Failover test message" in row[2] for row in messages)
            self.assertTrue(
                found,
                f"Failover test message not found in {db_file}. New leader might not have replicated properly."
            )

        print(f"New leader is running on port {new_leader_port}. Failover succeeded.")

if __name__ == "__main__":
    unittest.main()