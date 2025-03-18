from test_base import BaseTest
import chat_service_pb2

class TestAuthenticationRequired(BaseTest):
    def test_fetch_messages_without_login(self):
        """Test that fetch_messages fails if no user is logged in"""
        stub = self.stub
        
        # Try to fetch messages without logging in
        fetch_response = stub.FetchAwayMsgs(
            chat_service_pb2.FetchAwayMsgsRequest(
                auth_token="invalid_token",
                limit=5
            )
        )
        self.assertEqual(fetch_response.status, "error", 
            "❌ Test Failed: Fetching messages without login should not be allowed!")

    def test_send_message_without_login(self):
        """Test that send_message fails if no user is logged in"""
        stub = self.stub
        
        # Try to send message without logging in
        send_response = stub.SendMessage(
            chat_service_pb2.SendMessageRequest(
                auth_token="invalid_token",
                recipient="Bob",
                content="Hello Bob!"
            )
        )
        self.assertEqual(send_response.status, "error",
            "❌ Test Failed: Sending messages without login should not be allowed!")

    def test_user_cannot_send_as_another_user(self):
        """Test that a logged-in user cannot send messages as someone else"""
        stub = self.stub

        # Sign up Alice and Bob
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))
        stub.Signup(chat_service_pb2.SignupRequest(username="Bob", password="password"))

        # Login as Alice
        login_response = stub.Login(
            chat_service_pb2.LoginRequest(username="Alice", password="secret")
        )
        self.assertEqual(login_response.status, "ok")
        alice_token = login_response.auth_token

        # Try to send message as Bob while logged in as Alice
        send_response = stub.SendMessage(
            chat_service_pb2.SendMessageRequest(
                auth_token=alice_token,
                recipient="Charlie",
                content="Message from Alice as Bob!"
            )
        )
        self.assertEqual(send_response.status, "error",
            "❌ Test Failed: Alice should not be able to send messages as Bob!")

if __name__ == "__main__":
    import unittest
    unittest.main()