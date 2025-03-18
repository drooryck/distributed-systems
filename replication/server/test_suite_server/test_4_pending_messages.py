from test_base import BaseTest
import chat_service_pb2

class TestPendingMessages(BaseTest):
    def test_pending_messages(self):
        """Test that unread messages appear upon login"""

        # Reset the database
        self.reset_database()

        # Sign up Alice and Bob
        self.signup("Alice", "secret")
        self.signup("Bob", "bobpass")

        # Bob logs in and retrieves an auth token
        bob_login = self.login("Bob", "bobpass")
        self.assertEqual(bob_login.status, "ok")
        bob_token = bob_login.auth_token  # Bob's auth token

        # Bob sends two messages to Alice
        self.send_message(bob_token, "Alice", "Hey Alice!")
        self.send_message(bob_token, "Alice", "Message 2!")

        # Bob logs out
        logout_response = self.logout(bob_token)
        self.assertEqual(logout_response.status, "ok")

        # Alice logs in and retrieves an auth token
        alice_login = self.login("Alice", "secret")
        print(alice_login)  # Debug output
        self.assertEqual(alice_login.status, "ok")

        # Assert that Alice has at least 2 unread messages
        self.assertGreaterEqual(alice_login.unread_count, 2)

if __name__ == "__main__":
    import unittest
    unittest.main()
