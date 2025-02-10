from test_base import BaseTest

class TestSendMessage(BaseTest):
    def test_send_message(self):
        """Test that messages can be sent successfully"""
        self.reset_database()
        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("signup", {"username": "Bob", "password": "password"})
        self.receive_response()

        self.send_message("login", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("send_message", {"sender": "Alice", "recipient": "Bob", "content": "Hello Bob!"})
        response = self.receive_response()
        print()
        print(response)
        print()

        self.assertEqual(response["data"]["status"], "ok")
