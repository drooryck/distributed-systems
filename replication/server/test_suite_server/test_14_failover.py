import unittest
import subprocess
import time
import sqlite3
import os
import grpc

from test_base import BaseTest  # or adapt as needed
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

SERVER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server.py")


def start_server(server_id, port, db_file, peers):
    """
    Launch one server as a subprocess with no stdout/stderr capture.
    """
    cmd = [
        "python", SERVER_SCRIPT,
        f"--server_id={server_id}",
        f"--port={port}",
        f"--db_file={db_file}",
        f"--peers={peers}"
    ]
    return subprocess.Popen(cmd, stdout=None, stderr=None)


class TestFailover(BaseTest):
    """
    Tests failover by killing the initial leader (server #1) and ensuring a new leader
    is elected so that the cluster remains operational.
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
        # 1) Start all servers.
        self.procs = []
        for cfg in self.SERVERS:
            p = start_server(
                cfg["server_id"],
                cfg["port"],
                cfg["db_file"],
                cfg["peers"]
            )
            self.procs.append(p)
            time.sleep(0.5)

        # 2) Give them time to start
        time.sleep(10)

        # 3) Check if any server crashed on startup
        for i, proc in enumerate(self.procs):
            ret = proc.poll()
            if ret is not None:
                raise RuntimeError(
                    f"Server {self.SERVERS[i]['server_id']} crashed immediately "
                    f"with exit code: {ret}."
                )

        # 4) Connect to the assumed leader (server #1) and reset the DB
        self.leader_channel = grpc.insecure_channel("localhost:50051")
        self.leader_stub = chat_service_pb2_grpc.ChatServiceStub(self.leader_channel)

        # Sign up / login admin
        self.leader_stub.Signup(chat_service_pb2.SignupRequest(username="admin", password="adminpass"))
        admin_login = self.leader_stub.Login(chat_service_pb2.LoginRequest(username="admin", password="adminpass"))
        if admin_login.status != "ok":
            raise RuntimeError("Admin login failed; cannot reset DB")

        # Reset DB
        self.leader_stub.ResetDB(
            chat_service_pb2.EmptyRequest(auth_token=admin_login.auth_token)
        )
        time.sleep(2)  # Let reset replicate

    def tearDown(self):
        # Ensure all processes are terminated, no matter what.
        for p in self.procs:
            if p is not None:
                p.terminate()
                p.wait()
        # Close any channels
        self.leader_channel.close()

    def query_db(self, db_file, query, params=()):
        """
        Helper to run a query on the local SQLite DB file.
        """
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return rows

    def find_new_leader_stub(self, dead_server_ids=None, timeout_secs=10):
        """
        Polls each *live* server's ClusterInfo() endpoint to see who returns status="ok".
        That server is the leader, since the ClusterInfo() RPC is coded to return "NOT_LEADER"
        from followers.

        :param dead_server_ids: list of server_ids we know are dead or intentionally killed
                                (we skip them).
        :param timeout_secs: how many seconds to wait for a new leader to emerge.

        :return: (stub, channel) for the newly discovered leader
        :raises: RuntimeError if no leader is found within the timeout.
        """
        if dead_server_ids is None:
            dead_server_ids = []

        start_time = time.time()
        while (time.time() - start_time) < timeout_secs:
            for s in self.SERVERS:
                server_id = s["server_id"]
                if server_id in dead_server_ids:
                    continue  # skip known-dead servers

                addr = f"localhost:{s['port']}"
                channel = grpc.insecure_channel(addr)
                stub = chat_service_pb2_grpc.ChatServiceStub(channel)

                try:
                    # 'ClusterInfo' returns status="ok" if and only if that server is leader
                    resp = stub.ClusterInfo(chat_service_pb2.EmptyRequest(), timeout=1.0)
                    if resp.status == "ok":
                        # We found the new leader, return it
                        return stub, channel
                    # If it returned status="error", it's a follower or there's no leader yet
                except Exception:
                    # Possibly can't connect or times out if server isn't responding
                    pass

            time.sleep(1)

        raise RuntimeError(f"No new leader found within {timeout_secs} seconds.")

    def test_leader_failover(self):
        # STEP A: Perform some writes on the original leader (#1).
        # 1) Create Alice
        signup_alice = self.leader_stub.Signup(
            chat_service_pb2.SignupRequest(username="Alice", password="alicepass")
        )
        self.assertEqual(signup_alice.status, "ok", "Signup for Alice failed on original leader")

        # 2) Create Bob (so that sending him a message is valid)
        signup_bob = self.leader_stub.Signup(
            chat_service_pb2.SignupRequest(username="Bob", password="bobpass")
        )
        self.assertEqual(signup_bob.status, "ok", "Signup for Bob failed on original leader")

        # 3) Alice logs in and sends Bob a message
        login_alice = self.leader_stub.Login(
            chat_service_pb2.LoginRequest(username="Alice", password="alicepass")
        )
        self.assertEqual(login_alice.status, "ok", "Login for Alice failed on original leader")
        token_alice = login_alice.auth_token

        send_resp = self.leader_stub.SendMessage(
            chat_service_pb2.SendMessageRequest(
                auth_token=token_alice,
                recipient="Bob",
                content="Failover test message"
            )
        )
        self.assertEqual(send_resp.status, "ok", "SendMessage failed on original leader")
        time.sleep(2)  # let replication occur

        # STEP B: Kill the original leader (server #1).
        self.procs[0].terminate()
        self.procs[0].wait()
        self.procs[0] = None  # Mark that we've killed it.

        # STEP C: Wait for a new leader to be elected.
        new_leader_stub, new_leader_channel = self.find_new_leader_stub()

        # STEP D: Perform some writes on the new leader.
        # Let's sign up "Charlie"
        signup_charlie = new_leader_stub.Signup(
            chat_service_pb2.SignupRequest(username="Charlie", password="charliepass")
        )
        self.assertEqual(signup_charlie.status, "ok", "Signup for Charlie failed on new leader")

        # STEP E: Verify data is in each DB (#1, #2, #3). #1 is dead but we still check its file on disk.
        for s in self.SERVERS[1:]:
            db_file = s["db_file"]
            self.assertTrue(
                os.path.exists(db_file),
                f"DB file {db_file} does not exist"
            )

            # Check for "Alice"
            row = self.query_db(db_file, "SELECT username FROM users WHERE username=?", ("Alice",))
            self.assertTrue(len(row) > 0, f"Alice not found in {db_file}")

            # Check for "Bob"
            row = self.query_db(db_file, "SELECT username FROM users WHERE username=?", ("Bob",))
            self.assertTrue(len(row) > 0, f"Bob not found in {db_file}")

            # Check for the message from Alice to Bob
            msg_rows = self.query_db(
                db_file,
                "SELECT sender, recipient, content FROM messages WHERE sender='Alice' AND recipient='Bob'"
            )
            self.assertTrue(len(msg_rows) > 0, f"No message from Alice->Bob found in {db_file}")
            found = any("Failover test message" in row[2] for row in msg_rows)
            self.assertTrue(found, f"Expected content not found in {db_file}")

            # Check that Charlie is recognized
            row = self.query_db(db_file, "SELECT username FROM users WHERE username=?", ("Charlie",))
            self.assertTrue(len(row) > 0, f"Charlie not found in {db_file}")

        new_leader_channel.close()


if __name__ == "__main__":
    unittest.main()