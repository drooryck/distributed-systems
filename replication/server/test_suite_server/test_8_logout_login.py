from test_base import BaseTest
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

class TestLogoutLogin(BaseTest):
    def test_logout_and_login(self):
        """
        1. Sign up & log in as Alice
        2. Logout
        3. Attempt action while logged out (should fail)
        4. Log in again and confirm success
        """
        stub = self.stub

        # Sign up Alice
        signup_response = stub.Signup(
            chat_service_pb2.SignupRequest(username="Alice", password="secret")
        )
        self.assertEqual(signup_response.status, "ok")

        # Login Alice
        login_response = stub.Login(
            chat_service_pb2.LoginRequest(username="Alice", password="secret")
        )
        self.assertEqual(login_response.status, "ok", "❌ Should log in successfully")
        auth_token = login_response.auth_token

        # Logout
        logout_response = stub.Logout(
            chat_service_pb2.EmptyRequest(auth_token=auth_token)
        )
        self.assertEqual(logout_response.status, "ok", "❌ Logout should succeed")

        # Attempt action while logged out
        send_response = stub.SendMessage(
            chat_service_pb2.SendMessageRequest(
                auth_token=auth_token,  # Using old token
                recipient="Bob",
                content="Test message"
            )
        )
        self.assertEqual(send_response.status, "error", 
                        "❌ Should not allow sending while logged out")

        # Login again
        login_response = stub.Login(
            chat_service_pb2.LoginRequest(username="Alice", password="secret")
        )
        self.assertEqual(login_response.status, "ok", 
                        "❌ Should log in again after logout")

if __name__ == "__main__":
    import unittest
    unittest.main()