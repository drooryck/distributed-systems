from test_base import BaseTest

class TestPendingMessages(BaseTest):
    def test_pending_messages(self):
        """Test that unread messages appear upon login"""
        self.reset_database()
        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("signup", {"username": "Bob", "password": "bobpass"})
        self.receive_response()

        self.send_message("login", {"username": "Bob", "password": "bobpass"})
        self.receive_response()

        self.send_message("send_message", {"sender": "Bob", "recipient": "Alice", "content": "Hey Alice!"})
        self.receive_response()

        self.send_message("send_message", {"sender": "Bob", "recipient": "Alice", "content": "Message 2!"})
        self.receive_response()

        self.sock.close()

        self.setUp()  # Reconnect as Alice
        self.send_message("login", {"username": "Alice", "password": "secret"})
        response = self.receive_response()

        unread_count = response["data"]["unread_count"]
        self.assertGreaterEqual(unread_count, 2)
