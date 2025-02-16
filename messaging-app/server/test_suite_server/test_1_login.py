from test_base import BaseTest

class TestLogin(BaseTest):
    def test_valid_login(self):
        """Test a valid login"""
        self.send_message("reset_db", {}, is_response=False)
        response = self.receive_response()

        self.send_message("signup", {"username": "Alice", "password": "secret"}, is_response=0)
        response = self.receive_response()

        self.send_message("login", {"username": "Alice", "password": "secret"}, is_response=0)
        response = self.receive_response()

        print(response)
        self.assertEqual(response["status"], "ok")

    def test_invalid_login_twice(self):
        """Test logging in with multiple accounts from the same connection"""
        self.reset_database()
        self.send_message("signup", {"username": "Bob", "password": "password"}, is_response=0)
        self.receive_response()

        self.send_message("signup", {"username": "Alice", "password": "secret"}, is_response=0)
        self.receive_response()

        self.send_message("login", {"username": "Alice", "password": "secret"}, is_response=0)
        response = self.receive_response()

        self.send_message("login", {"username": "Bob", "password": "password"}, is_response=0)
        response = self.receive_response()
        print(response)
        self.assertEqual(response["status"], "error")

if __name__ == "__main__":
    import unittest
    unittest.main()