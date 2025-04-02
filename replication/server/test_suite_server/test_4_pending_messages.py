from test_base import BaseTest
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

class TestPendingMessages(BaseTest):
    def test_pending_messages(self):
        """Test that unread messages appear upon login"""
        
        stub = self.stub  # Get gRPC stub from BaseTest
        
        # Create an admin user to allow a reset.
        admin_signup = stub.Signup(chat_service_pb2.SignupRequest(username="admin", password="adminpass"))
        # Log in as admin to get an auth token.
        admin_login = stub.Login(chat_service_pb2.LoginRequest(username="admin", password="adminpass"))
        self.assertEqual(admin_login.status, "ok")
        admin_token = admin_login.auth_token
        
        # Reset the database using admin's auth token.
        reset_response = stub.ResetDB(chat_service_pb2.EmptyRequest(auth_token=admin_token))
        print("Reset response:", reset_response.status)  # Debug output.
        self.assertEqual(reset_response.status, "ok")

        # Confirm Alice has 0 messages immediately after reset
        alice_login = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        print("📦 After reset, Alice unread_count:", alice_login.unread_count)
        
        # Sign up Alice and Bob.
        signup_alice = stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))
        signup_bob = stub.Signup(chat_service_pb2.SignupRequest(username="Bob", password="bobpass"))
        
        # Bob logs in.
        bob_login = stub.Login(chat_service_pb2.LoginRequest(username="Bob", password="bobpass"))
        self.assertEqual(bob_login.status, "ok")
        bob_token = bob_login.auth_token
        
        # Bob sends two messages to Alice.
        send_resp1 = stub.SendMessage(chat_service_pb2.SendMessageRequest(
            auth_token=bob_token,
            recipient="Alice",
            content="Hey Alice!"
        ))
        send_resp2 = stub.SendMessage(chat_service_pb2.SendMessageRequest(
            auth_token=bob_token,
            recipient="Alice",
            content="Message 2!"
        ))
        self.assertEqual(send_resp1.status, "ok")
        self.assertEqual(send_resp2.status, "ok")
        
        # Bob logs out.
        logout_response = stub.Logout(chat_service_pb2.EmptyRequest(auth_token=bob_token))
        self.assertEqual(logout_response.status, "ok")
        
        # Alice logs in.
        alice_login = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        print("Alice login response:", alice_login)  # Debug output.
        self.assertEqual(alice_login.status, "ok")
        
        # Assert that Alice has at least 2 unread messages.
        print("Full Alice login response:", repr(alice_login))
        print("unread_count field:", alice_login.unread_count)
        self.assertGreaterEqual(alice_login.unread_count, 2)

if __name__ == "__main__":
    import unittest
    unittest.main()