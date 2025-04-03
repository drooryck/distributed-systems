import unittest
import subprocess
import time
import sqlite3
import os
import psutil
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

def kill_all_chat_servers():
    """
    This kills any 'python server.py' processes still running from previous tests.
    Requires 'pip install psutil'.
    """
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


class TestDoubleFailover(BaseTest):
    """
    Demonstrates killing two consecutive leaders in a 3-server cluster.
    1) Kills original leader (#1).
    2) Finds new leader (#2 or #3), kills it.
    3) Ensures the last server (#2 or #3) still has the data.
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
        kill_all_chat_servers()

        # Launch all 3 servers
        self.procs = []
        for cfg in self.SERVERS:
            p = start_server(
                cfg["server_id"],
                cfg["port"],
                cfg["db_file"],
                cfg["peers"]
            )
            self.procs.append(p)
            time.sleep(0.1)

        time.sleep(7)  # Let them start up

        # Verify none crashed on startup
        for i, proc in enumerate(self.procs):
            ret = proc.poll()
            if ret is not None:
                raise RuntimeError(
                    f"Server {self.SERVERS[i]['server_id']} crashed on startup (exit code={ret})."
                )

        # Connect to original leader (#1) on port 50051, reset DB
        self.leader_channel = grpc.insecure_channel("localhost:50051")
        self.leader_stub = chat_service_pb2_grpc.ChatServiceStub(self.leader_channel)

        # Create admin, reset DB
        self.leader_stub.Signup(chat_service_pb2.SignupRequest(username="admin", password="adminpass"))
        admin_login = self.leader_stub.Login(chat_service_pb2.LoginRequest(username="admin", password="adminpass"))
        if admin_login.status != "ok":
            raise RuntimeError("Could not login as admin on server #1")

        self.leader_stub.ResetDB(
            chat_service_pb2.EmptyRequest(auth_token=admin_login.auth_token)
        )
        time.sleep(2)  # Let reset replicate

    def tearDown(self):
        # Terminate all server processes
        for p in self.procs:
            if p is not None:
                p.terminate()
                p.wait()

        # Close leader channel
        self.leader_channel.close()

    def query_db(self, db_file, query, params=()):
        """
        Helper to query local DB for final checks.
        """
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return rows

    def find_leader_stub(self, dead_ids=None, timeout_secs=10):
        """
        Return a stub to whichever server is currently the leader,
        skipping any known-dead server IDs.
        """
        if dead_ids is None:
            dead_ids = []
        start = time.time()
        while time.time() - start < timeout_secs:
            for s in self.SERVERS:
                if s["server_id"] in dead_ids:
                    continue
                channel = grpc.insecure_channel(f"localhost:{s['port']}")
                stub = chat_service_pb2_grpc.ChatServiceStub(channel)
                try:
                    resp = stub.ClusterInfo(chat_service_pb2.EmptyRequest(), timeout=1.0)
                    if resp.status == "ok":  # This node claims it is leader
                        return stub, channel, s["server_id"]
                except:
                    pass
            time.sleep(1)

        raise RuntimeError("No leader found within timeout")

    def test_double_leader_failover(self):
        ### Step A: Original cluster with leader #1
        # Sign up Alice, Bob, Alice -> Bob message
        self.leader_stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="alicepass"))
        self.leader_stub.Signup(chat_service_pb2.SignupRequest(username="Bob", password="bobpass"))
        login_alice = self.leader_stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="alicepass"))
        self.assertEqual(login_alice.status, "ok", "Failed to log in Alice on server #1")
        token_alice = login_alice.auth_token
        send_resp = self.leader_stub.SendMessage(
            chat_service_pb2.SendMessageRequest(
                auth_token=token_alice,
                recipient="Bob",
                content="Double-failover test message"
            )
        )
        self.assertEqual(send_resp.status, "ok")

        time.sleep(2)  # replicate

        ### Step B: Kill leader #1
        self.procs[0].terminate()
        self.procs[0].wait()
        self.procs[0] = None
        dead_ids = [1]

        ### Step C: find new leader among #2, #3
        new_stub, new_channel, new_leader_id = self.find_leader_stub(dead_ids=dead_ids)
        # sign up "Charlie"
        signup_charlie = new_stub.Signup(chat_service_pb2.SignupRequest(username="Charlie", password="charliepass"))
        self.assertEqual(signup_charlie.status, "ok", "Failed to sign up Charlie on new leader")

        time.sleep(2)

        ### Step D: Kill second leader (the one we just found)
        idx = next(i for i,srv in enumerate(self.SERVERS) if srv["server_id"] == new_leader_id)
        self.procs[idx].terminate()
        self.procs[idx].wait()
        self.procs[idx] = None
        dead_ids.append(new_leader_id)
        new_channel.close()

        ### Step E: Only one server left alive => that server must be leader
        final_stub, final_channel, final_leader_id = self.find_leader_stub(dead_ids=dead_ids)
        self.assertNotIn(final_leader_id, dead_ids, "The final leader is marked as dead? Logic error.")

        # Step F: do final writes: sign up "Dave"
        signup_dave = final_stub.Signup(chat_service_pb2.SignupRequest(username="Dave", password="davepass"))
        self.assertEqual(signup_dave.status, "ok", "Failed to sign up Dave on final leader")

        time.sleep(2)

        # Step G: verify that the final server has Alice, Bob, Charlie, Dave
        for s in self.SERVERS:
            # skip dead servers
            if s["server_id"] in dead_ids:
                continue
            db_file = s["db_file"]
            # each live server is either the final node or a leftover follower (the latter shouldn’t happen with 2 kills)
            # but let's just confirm we can query it, if it’s still around

            # Confirm Alice
            row = self.query_db(db_file, "SELECT username FROM users WHERE username=?", ("Alice",))
            self.assertTrue(row, f"Alice missing in {db_file}")

            # Confirm Bob
            row = self.query_db(db_file, "SELECT username FROM users WHERE username=?", ("Bob",))
            self.assertTrue(row, f"Bob missing in {db_file}")

            # Confirm the message from Alice->Bob
            msgs = self.query_db(
                db_file,
                "SELECT content FROM messages WHERE sender='Alice' AND recipient='Bob'"
            )
            self.assertTrue(msgs, f"No Alice->Bob messages in {db_file}")
            self.assertTrue(any("Double-failover test message" in m[0] for m in msgs),
                            f"Missing 'Double-failover test message' in {db_file}")

            # Confirm Charlie
            row = self.query_db(db_file, "SELECT username FROM users WHERE username=?", ("Charlie",))
            self.assertTrue(row, f"Charlie missing in {db_file}")

            # Confirm Dave
            row = self.query_db(db_file, "SELECT username FROM users WHERE username=?", ("Dave",))
            self.assertTrue(row, f"Dave missing in {db_file}")

        final_channel.close()


if __name__ == "__main__":
    unittest.main()