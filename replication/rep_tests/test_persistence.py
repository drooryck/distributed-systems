import os
import time
import subprocess
import unittest
import grpc
import chat_service_pb2
import chat_service_pb2_grpc

# Points to ../server/server.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PATH = os.path.join(BASE_DIR, "server", "server.py")

PRIMARY_CMD = [
    "python",
    SERVER_PATH,
    "--port", "50051",
    "--db_file", "persistence_test.db",
    "--role", "primary"
]

class TestPersistence(unittest.TestCase):
    def setUp(self):
        """Remove old DB file, start server, wait for it to be ready."""
        if os.path.exists("persistence_test.db"):
            os.remove("persistence_test.db")

        self.proc = subprocess.Popen(PRIMARY_CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(2)  # Give it time to bind and create tables

        # Connect to the server
        channel = grpc.insecure_channel("localhost:50051")
        self.stub = chat_service_pb2_grpc.ChatServiceStub(channel)

        # Force the DB to reset by admin
        self._reset_database()

    def tearDown(self):
        """Kill the server process."""
        self.proc.terminate()
        self.proc.wait(timeout=5)

    def _reset_database(self):
        """
        1) Ensure an 'admin' user exists (Signup).
        2) Log in as admin to get auth_token.
        3) Call ResetDB to drop & recreate tables, guaranteeing an empty DB.
        """
        # Step 1) Attempt to sign up admin
        self.stub.Signup(
            chat_service_pb2.SignupRequest(username="admin", password="adminpass")
        )

        # Step 2) Log in as admin
        admin_login = self.stub.Login(
            chat_service_pb2.LoginRequest(username="admin", password="adminpass")
        )
        if admin_login.status != "ok":
            raise RuntimeError(f"Could not log in as admin to reset DB: {admin_login.msg}")

        # Step 3) Send ResetDB request
        reset_req = chat_service_pb2.EmptyRequest(auth_token=admin_login.auth_token)
        resp = self.stub.ResetDB(reset_req)
        if resp.status != "ok":
            raise RuntimeError(f"ResetDB failed: {resp.msg}")

        print("✅ DB was forcibly reset via admin. Should be empty now.")

    def test_persistence_after_restart(self):
        """
        1) Sign up 'Alice'
        2) Send a message from Alice to 'Bob'
        3) Kill the server
        4) Restart the server with the same DB
        5) Confirm Alice can still log in
        """
        # 1) Sign up 'Alice'
        signup_resp = self.stub.Signup(
            chat_service_pb2.SignupRequest(username="Alice", password="secret")
        )
        print("DEBUG: Signup returned:", signup_resp.status, signup_resp.msg)
        self.assertEqual(signup_resp.status, "ok", "Alice sign-up should be ok on empty DB")

        # 2) Alice logs in
        login_resp = self.stub.Login(
            chat_service_pb2.LoginRequest(username="Alice", password="secret")
        )
        self.assertEqual(login_resp.status, "ok")
        alice_token = login_resp.auth_token

        # 3) Send message to Bob
        send_resp = self.stub.SendMessage(
            chat_service_pb2.SendMessageRequest(
                auth_token=alice_token,
                recipient="Bob",
                content="Persistent Hello!"
            )
        )
        # Bob might not exist => "error" is acceptable. Checking for "ok" or "error"
        self.assertIn(send_resp.status, ["ok", "error"])

        # 4) Kill the server
        self.proc.terminate()
        self.proc.wait(timeout=5)

        # 5) Restart the server with the same DB
        #    We do not remove 'persistence_test.db' this time, to test persistence
        self.proc = subprocess.Popen(PRIMARY_CMD)
        time.sleep(2)

        # Recreate the stub after the restart
        channel2 = grpc.insecure_channel("localhost:50051")
        stub2 = chat_service_pb2_grpc.ChatServiceStub(channel2)

        # 6) Alice logs in again => proves user data persisted
        login_resp2 = stub2.Login(
            chat_service_pb2.LoginRequest(username="Alice", password="secret")
        )
        self.assertEqual(login_resp2.status, "ok",
            "❌ If DB data was lost, login would fail. The test proves data persisted.")

        print("✅ Test passed: Data persisted across a server restart!")

if __name__ == "__main__":
    unittest.main()