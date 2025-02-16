from test_base import BaseTest

class TestPendingMessages(BaseTest):
    def test_pending_messages(self):
        """Test that unread messages appear upon login"""
        self.reset_database()
        self.send_message("signup", {"username": "Alice", "password": "secret"}, is_response=0)
        self.receive_response()

        self.send_message("signup", {"username": "Bob", "password": "bobpass"}, is_response=0)
        self.receive_response()

        self.send_message("login", {"username": "Bob", "password": "bobpass"}, is_response=0)
        self.receive_response()

        self.send_message("send_message", {"sender": "Bob", "recipient": "Alice", "content": "Hey Alice!"}, is_response=0)
        self.receive_response()

        self.send_message("send_message", {"sender": "Bob", "recipient": "Alice", "content": "Message 2!"}, is_response=0)
        self.receive_response()

        self.send_message("logout", {}, is_response=0)
        response = self.receive_response()
        self.send_message("login", {"username": "Alice", "password": "secret"}, is_response=0)
        response = self.receive_response()
        print(response)
        
        unread_count = response["unread_count"]
        self.assertGreaterEqual(unread_count, 2)
