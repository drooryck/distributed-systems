import unittest
import subprocess
import time
import sqlite3
import os
import grpc
import psutil

from test_base import BaseTest  # or adapt to your environment
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

def kill_all_chat_servers():
    """
    This kills any 'python server.py' processes still running from previous tests.
    Requires 'pip install psutil'.
    """
    if not psutil:
        print("psutil not available; skipping leftover process cleanup.")
        return

    for proc in psutil.process_iter(attrs=["pid", "cmdline"]):
        cmdline = proc.info["cmdline"]
        if cmdline and "server.py" in " ".join(cmdline):
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                proc.kill()
            except Exception as e:
                print(f"Warning: Could not terminate leftover server {proc.pid}: {e}")


class TestRejoin(BaseTest):
    """
    Verifies that a brand-new server (with a fresh DB file) can be added to an
    existing 3-server cluster, obtains a snapshot from the leader, and ends up
    fully synchronized with the cluster state.
    """

    # Initial 3 servers in the cluster
    SERVERS_3 = [
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

    # The brand new server we want to add to the cluster
    NEW_SERVER = {
        "server_id": 4,
        "port": 50054,
        "db_file": "test_chat4.db",
        # We'll pass the entire cluster as peers, so it can find the leader
        "peers": "1:127.0.0.1:50051,2:127.0.0.1:50052,3:127.0.0.1:50053"
    }

    def setUp(self):
        kill_all_chat_servers()
        # 1) Start the original 3-server cluster
        self.procs = []
        for cfg in self.SERVERS_3:
            p = start_server(
                cfg["server_id"],
                cfg["port"],
                cfg["db_file"],
                cfg["peers"]
            )
            self.procs.append(p)

        # 2) Give them time to start
        time.sleep(7)

        # 3) Check if any server crashed on startup
        for i, proc in enumerate(self.procs):
            ret = proc.poll()
            if ret is not None:
                raise RuntimeError(
                    f"Server {self.SERVERS_3[i]['server_id']} crashed immediately "
                    f"with exit code: {ret}."
                )

        # 4) Connect to the assumed leader (server #1) and reset the DB
        self.leader_channel = grpc.insecure_channel("localhost:50051")
        self.leader_stub = chat_service_pb2_grpc.ChatServiceStub(self.leader_channel)

        # Sign up / login admin
        self.leader_stub.Signup(
            chat_service_pb2.SignupRequest(username="admin", password="adminpass")
        )
        admin_login = self.leader_stub.Login(
            chat_service_pb2.LoginRequest(username="admin", password="adminpass")
        )
        if admin_login.status != "ok":
            raise RuntimeError("Admin login failed; cannot reset DB")

        # Reset DB
        self.leader_stub.ResetDB(
            chat_service_pb2.EmptyRequest(auth_token=admin_login.auth_token)
        )
        time.sleep(2)  # Let reset replicate

    def tearDown(self):
        # Terminate all running servers, even if one of them failed earlier
        for i, p in enumerate(self.procs):
            if p is not None:
                try:
                    p.terminate()
                    p.wait(timeout=5)
                except Exception as e:
                    print(f"Warning: Failed to cleanly terminate server {i+1}: {e}")
                    try:
                        p.kill()
                    except Exception:
                        pass
        self.procs.clear()

        # Close any open gRPC channel
        if hasattr(self, "leader_channel"):
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

    def test_add_new_server_and_sync(self):
        # STEP A: Do some writes on the original cluster (ex: sign up user "Alice").
        signup_alice = self.leader_stub.Signup(
            chat_service_pb2.SignupRequest(username="Alice", password="alicepass")
        )
        self.assertEqual(signup_alice.status, "ok", "Signup for Alice failed on original leader")

        # Wait a bit for replication among the 3-server cluster
        time.sleep(1)

        # STEP B: Start the brand-new server #4 with an empty DB
        # Make sure test_chat4.db is removed to prove it loads from snapshot
        if os.path.exists(self.NEW_SERVER["db_file"]):
            os.remove(self.NEW_SERVER["db_file"])

        p4 = start_server(
            self.NEW_SERVER["server_id"],
            self.NEW_SERVER["port"],
            self.NEW_SERVER["db_file"],
            self.NEW_SERVER["peers"]
        )
        self.procs.append(p4)
        time.sleep(4)  # Let #4 come up, call join_cluster_if_needed, get snapshot

        # STEP C: Verify that server #4 now has "Alice" in its DB
        rows = self.query_db(self.NEW_SERVER["db_file"],
                             "SELECT username FROM users WHERE username=?",
                             ("Alice",))
        self.assertTrue(rows, "New server #4 did not receive 'Alice' from the leader snapshot")


        # If we reach here without an assertion error, the new server was successfully added
        # and it has the full data from the cluster.


if __name__ == "__main__":
    unittest.main()