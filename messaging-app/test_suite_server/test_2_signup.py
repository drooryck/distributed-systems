from test_base import BaseTest

class TestSignup(BaseTest):
    def test_multiple_signups(self):
        """Test that multiple accounts can be created"""
        self.reset_database()
        self.send_message("signup", {"username": "Charlie", "password": "abc123"}, is_response=0)
        self.receive_response()

        self.send_message("signup", {"username": "Dave", "password": "xyz789"}, is_response=0)
        response = self.receive_response()
        print(response)
        self.assertEqual(response["status"], "ok")