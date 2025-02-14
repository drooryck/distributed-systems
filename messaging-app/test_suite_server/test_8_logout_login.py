from test_base import BaseTest

class TestLogoutLogin(BaseTest):
    def test_logout_and_login(self):
        """
        1. Sign up & log in as Alice
        2. Logout
        3. Attempt action while logged out (should fail)
        4. Log in again and confirm success
        """
        self.reset_database()

        # Sign up Alice
        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        # Login Alice
        self.send_message("login", {"username": "Alice", "password": "secret"})
        response = self.receive_response()
        self.assertEqual(response["status"], "ok", "❌ Should log in successfully")

        # Logout
        self.send_message("logout", {})
        response = self.receive_response()
        self.assertEqual(response["status"], "ok", "❌ Logout should succeed")

        # Attempt action while logged out
        self.send_message("send_message", {"sender": "Alice", "recipient": "Bob", "content": "Test message"})
        response = self.receive_response()
        self.assertEqual(response["status"], "error", "❌ Should not allow sending while logged out")

        # Login again
        self.send_message("login", {"username": "Alice", "password": "secret"})
        response = self.receive_response()
        self.assertEqual(response["status"], "ok", "❌ Should log in again after logout")


if __name__ == "__main__":
    import unittest
    unittest.main()
