from test_base import BaseTest
import chat_service_pb2

class TestLogin(BaseTest):
    def test_valid_login(self):
        """Test a valid login"""
        stub = self.stub

        # Sign up first
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))

        # Log in and get auth token
        login_response = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        self.assertEqual(login_response.status, "ok")
        self.assertTrue(login_response.auth_token)

    def test_invalid_login_twice(self):
        """Test logging in with multiple accounts from the same connection"""
        stub = self.stub

        # Sign up users
        stub.Signup(chat_service_pb2.SignupRequest(username="Bob", password="password"))
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))

        # Log in Alice first
        login_response1 = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        self.assertEqual(login_response1.status, "ok")
        auth_token1 = login_response1.auth_token

        # Log in Bob
        login_response2 = stub.Login(chat_service_pb2.LoginRequest(username="Bob", password="password"))
        self.assertEqual(login_response2.status, "ok")
        auth_token2 = login_response2.auth_token

        # Verify different tokens for different users
        self.assertNotEqual(auth_token1, auth_token2)

if __name__ == "__main__":
    import unittest
    unittest.main()
