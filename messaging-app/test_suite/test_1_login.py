from test_base import BaseTest

class TestLogin(BaseTest):
    def test_valid_login(self):
        """Test a valid login"""
        self.reset_database()
        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("login", {"username": "Alice", "password": "secret"})
        response = self.receive_response()

        self.assertEqual(response["data"]["status"], "ok")

    def test_invalid_login_twice(self):
        """Test logging in with multiple accounts from the same connection"""
        self.reset_database()
        self.send_message("signup", {"username": "Bob", "password": "password"})
        self.receive_response()

        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("login", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("login", {"username": "Bob", "password": "password"})
        response = self.receive_response()

        self.assertEqual(response["data"]["status"], "error")

if __name__ == "__main__":
    import unittest
    unittest.main()