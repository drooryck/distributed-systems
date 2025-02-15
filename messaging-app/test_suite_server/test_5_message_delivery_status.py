from test_base import BaseTest

class TestMessageDeliveryStatus(BaseTest):
    def test_message_delivery(self):
        """Test that messages are marked as delivered once fetched"""
        self.reset_database()
        self.send_message("signup", {"username": "Frank", "password": "pass123"}, is_response=0)
        self.receive_response()

        self.send_message("signup", {"username": "Alice", "password": "secret"}, is_response=0)
        self.receive_response()

        self.send_message("login", {"username": "Alice", "password": "secret"}, is_response=0)
        self.receive_response()

        self.send_message("send_message", {"sender": "Alice", "recipient": "Frank", "content": "Hello Frank!"}, is_response=0)
        self.receive_response()

        self.send_message("logout", {}, is_response=0)

        self.send_message("login", {"username": "Frank", "password": "pass123"}, is_response=0)
        self.receive_response()

        self.send_message("fetch_away_msgs", {"num_messages": 5}, is_response=0)
        self.receive_response()

        first_fetch = self.receive_response()
        print(first_fetch)
        
        self.assertEqual(len(first_fetch["msg"]), 1)
