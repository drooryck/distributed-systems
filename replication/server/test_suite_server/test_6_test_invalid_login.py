import unittest
from test_base import BaseTest
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

class TestInvalidLogin(BaseTest):
    def test_login_wrong_password(self):
        """Test logging in with an incorrect password"""
        stub = self.stub
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="correct_password"))
        response = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="wrong_password"))
        self.assertEqual(response.msg, "Incorrect password", "❌ Test Failed: Wrong error message for incorrect password!")
        print("✅ test_login_wrong_password: Cannot log in with wrong password.")

    def test_login_missing_password(self):
        """Test that login fails if the password is missing"""
        stub = self.stub
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="correct_password"))
        response = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password=""))
        self.assertEqual(response.msg, "Username/password required", "❌ Test Failed: Wrong error message for missing password!")
        print("✅ test_login_missing_password: Server rejects missing password.")

    def test_login_missing_username(self):
        """Test that login fails if the username is missing"""
        stub = self.stub
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="correct_password"))
        response = stub.Login(chat_service_pb2.LoginRequest(username="", password="correct_password"))
        self.assertEqual(response.msg, "Username/password required", "❌ Test Failed: Wrong error message for missing username!")
        print("✅ test_login_missing_username: Server rejects missing username.")

    def test_login_non_existent_user(self):
        """Test logging in with a non-existent user"""
        stub = self.stub
        response = stub.Login(chat_service_pb2.LoginRequest(username="GhostUser", password="password123"))
        self.assertEqual(response.msg, "Username not found", "❌ Test Failed: Wrong error message for non-existent user!")
        print("✅ test_login_non_existent_user: Cannot log in with unregistered user.")
if __name__ == "__main__":
    unittest.main()
