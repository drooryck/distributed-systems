from test_base import BaseTest

class TestAuthenticationRequired(BaseTest):
    def test_fetch_messages_without_login(self):
        """Test that fetch_messages fails if no user is logged in"""
        self.reset_database()
        self.send_message("fetch_away_msgs", {"num_messages": 5}, is_response=0)
        response = self.receive_response()
        self.assertEqual(response["status"], "error", "❌ Test Failed: Fetching messages without login should not be allowed!")

    def test_send_message_without_login(self):
        """Test that send_message fails if no user is logged in"""
        self.reset_database()
        self.send_message("send_message", {"sender": "Alice", "recipient": "Bob", "content": "Hello Bob!"}, is_response=0)
        response = self.receive_response()
        self.assertEqual(response["status"], "error", "❌ Test Failed: Sending messages without login should not be allowed!")

    def test_user_cannot_send_as_another_user(self):
        """Test that a logged-in user cannot send messages as someone else"""
        self.reset_database()
        
        self.send_message("signup", {"username": "Alice", "password": "secret"}, is_response=0)
        self.receive_response()

        self.send_message("signup", {"username": "Bob", "password": "password"}, is_response=0)
        self.receive_response()

        self.send_message("login", {"username": "Alice", "password": "secret"}, is_response=0)
        self.receive_response()

        self.send_message("send_message", {"sender": "Bob", "recipient": "Charlie", "content": "Message from Alice as Bob!"}, is_response=0)
        response = self.receive_response()
        self.assertEqual(response["status"], "error", "❌ Test Failed: Alice should not be able to send messages as Bob!")

if __name__ == "__main__":
    import unittest
    unittest.main()
