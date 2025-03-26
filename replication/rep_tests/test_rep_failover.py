import os
import time
import subprocess
import unittest
import grpc
import chat_service_pb2
import chat_service_pb2_grpc

# Compute absolute path to server.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PATH = os.path.join(BASE_DIR, "server", "server.py")

# Commands to launch your servers
PRIMARY_CMD = [
    "python",
    SERVER_PATH,
    "--port", "50051",
    "--db_file", "repl_primary.db",
    "--role", "primary",
    "--backups", "localhost:50052,localhost:50053"
]
BACKUP1_CMD = [
    "python",
    SERVER_PATH,
    "--port", "50052",
    "--db_file", "repl_backup1.db",
    "--role", "backup"
]
BACKUP2_CMD = [
    "python",
    SERVER_PATH,
    "--port", "50053",
    "--db_file", "repl_backup2.db",
    "--role", "backup"
]

def get_stub(port=50051):
    channel = grpc.insecure_channel(f"localhost:{port}")
    return chat_service_pb2_grpc.ChatServiceStub(channel)

class TestReplicationFailover(unittest.TestCase):
    def setUp(self):
        """Wipe old DB files, start primary + 2 backups, and reset the DB on the primary."""
        for filename in ["repl_primary.db", "repl_backup1.db", "repl_backup2.db"]:
            if os.path.exists(filename):
                os.remove(filename)

        self.proc_primary = subprocess.Popen(PRIMARY_CMD)
        self.proc_backup1 = subprocess.Popen(BACKUP1_CMD)
        self.proc_backup2 = subprocess.Popen(BACKUP2_CMD)
        time.sleep(3)  # Allow servers time to boot

        self.stub_primary = get_stub(50051)

        # Forcefully reset the DB
        self._reset_database_on_primary()

    def tearDown(self):
        """Kill all subprocesses."""
        for proc in [self.proc_primary, self.proc_backup1, self.proc_backup2]:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _reset_database_on_primary(self):
        """Sign up admin and reset DB on primary server."""
        # Step 1: Signup admin (ignore failure)
        self.stub_primary.Signup(chat_service_pb2.SignupRequest(
            username="admin", password="adminpass"
        ))

        # Step 2: Login admin
        login_resp = self.stub_primary.Login(chat_service_pb2.LoginRequest(
            username="admin", password="adminpass"
        ))
        self.assertEqual(login_resp.status, "ok", f"Admin login failed: {login_resp.msg}")

        # Step 3: Reset DB
        reset_resp = self.stub_primary.ResetDB(chat_service_pb2.EmptyRequest(
            auth_token=login_resp.auth_token
        ))
        self.assertEqual(reset_resp.status, "ok", f"ResetDB failed: {reset_resp.msg}")
        print("✅ DB forcibly reset on primary. It should now be empty.")

    def test_failover_and_data_integrity(self):
        """
        1. Sign up 'Alice' and send a message via the primary.
        2. Kill the primary.
        3. Attempt login from backup.
        """
        # 1) Sign up Alice
        resp = self.stub_primary.Signup(chat_service_pb2.SignupRequest(
            username="Alice", password="secret"
        ))
        print("DEBUG Signup =>", resp.status, resp.msg)
        self.assertEqual(resp.status, "ok")

        # Login Alice
        login_resp = self.stub_primary.Login(chat_service_pb2.LoginRequest(
            username="Alice", password="secret"
        ))
        self.assertEqual(login_resp.status, "ok")
        alice_token = login_resp.auth_token

        # Send message to Bob
        send_resp = self.stub_primary.SendMessage(chat_service_pb2.SendMessageRequest(
            auth_token=alice_token,
            recipient="Bob",
            content="Hello from replication test"
        ))
        self.assertIn(send_resp.status, ["ok", "error"])

        # 2) Kill the primary
        self.proc_primary.terminate()
        self.proc_primary.wait(timeout=5)
        time.sleep(2)

        # 3) Connect to backup #1
        stub_backup1 = get_stub(50052)

        # Attempt to log in as Alice from the backup
        login_resp_b1 = stub_backup1.Login(chat_service_pb2.LoginRequest(
            username="Alice", password="secret"
        ))

        if login_resp_b1.status == "ok":
            print("✅ Backup recognized 'Alice' user → replication succeeded.")
        else:
            print(f"⚠️ Login failed on backup: {login_resp_b1.msg}")

        # Pass if Alice is known on backup
        self.assertEqual(login_resp_b1.status, "ok", "❌ Replication failed – user not present on backup.")

if __name__ == "__main__":
    unittest.main()