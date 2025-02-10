from test_base import BaseTest

class TestMessageDeliveryStatus(BaseTest):
    def test_message_delivery(self):
        """Test that messages are marked as delivered once fetched"""
        self.reset_database()
        self.send_message("signup", {"username": "Frank", "password": "pass123"})
        self.receive_response()

        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("login", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("send_message", {"sender": "Alice", "recipient": "Frank", "content": "Hello Frank!"})
        self.receive_response()

        self.sock.close()

        self.setUp()  # Reconnect as Frank
        self.send_message("login", {"username": "Frank", "password": "pass123"})
        self.receive_response()

        self.send_message("fetch_messages", {"num_messages": 5})
        first_fetch = self.receive_response()

        self.assertEqual(len(first_fetch["data"]["messages"]), 1)
