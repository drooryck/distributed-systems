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


SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server.py")

def start_server(server_id, port, db_file, peers):
    """
    Helper to launch one server as a subprocess with no stdout/stderr capture.
    """
    cmd = [
        "python", "../server.py",  # or SERVER_SCRIPT, if that path is correct for your project
        f"--server_id={server_id}",
        f"--port={port}",
        f"--db_file={db_file}",
        f"--peers={peers}"
    ]
    return subprocess.Popen(cmd, stdout=None, stderr=None)

class TestReplication(BaseTest):
    """
    Spawns a 3-server cluster, performs replication test, and verifies
    that user accounts and messages appear in each server's DB.
    """

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

        # 2) Wait for them to start up
        time.sleep(10)

        # 3) Check if any server crashed immediately; if so, raise an error
        for i, proc in enumerate(self.procs):
            retcode = proc.poll()
            if retcode is not None:
                stdout, stderr = proc.communicate()
                raise RuntimeError(
                    f"Server {self.SERVERS[i]['server_id']} crashed on startup. "
                    f"Exit code: {retcode}\n--- STDOUT ---\n{stdout}\n"
                    f"--- STDERR ---\n{stderr}\n"
                )

        # 4) Connect to the assumed leader (port 50051) and reset the DB
        self.channel = grpc.insecure_channel("localhost:50051")
        self.stub = chat_service_pb2_grpc.ChatServiceStub(self.channel)

        # Sign up admin (if not exists) and reset DB
        self.stub.Signup(chat_service_pb2.SignupRequest(username="admin", password="adminpass"))
        admin_login = self.stub.Login(chat_service_pb2.LoginRequest(username="admin", password="adminpass"))
        if admin_login.status != "ok":
            raise RuntimeError("Admin login failed; cannot reset DB")

        self.stub.ResetDB(chat_service_pb2.EmptyRequest(auth_token=admin_login.auth_token))
        # Wait a bit for the reset to propagate to all servers
        time.sleep(2)

    def tearDown(self):
        # Kill *all* servers, even if one crashed or was None
        for proc in self.procs:
            if proc is not None:
                proc.terminate()
                proc.wait()
        # Close the gRPC channel
        self.channel.close()

    def query_db(self, db_file, query, params=()):
        """Helper to query a SQLite database file."""
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(query, params)
        results = c.fetchall()
        conn.close()
        return results

    def test_replication_across_servers(self):
        # 1) Create users Alice and Bob on the leader
        signup_alice = self.stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))
        self.assertEqual(signup_alice.status, "ok", "Signup for Alice failed on leader")

        signup_bob = self.stub.Signup(chat_service_pb2.SignupRequest(username="Bob", password="passB"))
        self.assertEqual(signup_bob.status, "ok", "Signup for Bob failed on leader")

        # 2) Login as Alice to get an auth token
        login_alice = self.stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        self.assertEqual(login_alice.status, "ok", "Login for Alice failed on leader")
        token_alice = login_alice.auth_token

        # 3) Alice sends message to Bob
        send_response = self.stub.SendMessage(
            chat_service_pb2.SendMessageRequest(
                auth_token=token_alice,
                recipient="Bob",
                content="Replication test message"
            )
        )
        self.assertEqual(send_response.status, "ok", "Send message failed on leader")

        # 4) Wait for replication
        time.sleep(2)

        # 5) Check that both users and the message are in each server's DB
        for cfg in self.SERVERS:
            db_file = cfg["db_file"]
            self.assertTrue(os.path.exists(db_file), f"DB file {db_file} does not exist")

            # Confirm users
            users = self.query_db(
                db_file,
                "SELECT username FROM users WHERE username IN (?, ?)",
                ("Alice", "Bob")
            )
            usernames = [row[0] for row in users]
            self.assertIn("Alice", usernames, f"Alice not found in {db_file}")
            self.assertIn("Bob", usernames, f"Bob not found in {db_file}")

            # Confirm the message from Alice to Bob
            messages = self.query_db(
                db_file,
                "SELECT sender, recipient, content FROM messages WHERE sender=? AND recipient=?",
                ("Alice", "Bob")
            )
            self.assertGreaterEqual(
                len(messages), 1,
                f"No message from Alice to Bob found in {db_file}"
            )
            found = any("Replication test message" in row[2] for row in messages)
            self.assertTrue(
                found,
                f"Expected message content not found in {db_file}"
            )


if __name__ == "__main__":
    unittest.main()