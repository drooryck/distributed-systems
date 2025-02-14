from test_base import BaseTest

class TestDeleteAccount(BaseTest):
    def test_cannot_delete_without_login(self):
        """
        1. Ensure that trying to delete an account while not logged in returns an error.
        """
        self.reset_database()

        # Attempt to delete account without logging in
        self.send_message("delete_account", {})
        response = self.receive_response()

        self.assertEqual(response["status"], "error", "❌ Should fail if no user is logged in.")
        self.assertIn("not currently logged in", response["msg"], "❌ Error message should indicate no login.")

    def test_delete_account_removes_user_and_messages(self):
        """
        1. Sign up and log in as Alice
        2. Alice sends messages to Bob
        3. Alice deletes her account
        4. Confirm:
           - The user record is gone (can't log in again)
           - Messages from/to Alice are removed
        """
        self.reset_database()

        # Sign up Bob
        self.send_message("signup", {"username": "Bob", "password": "bobpass"})
        self.receive_response()

        # Sign up Alice
        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        # Alice logs in
        self.send_message("login", {"username": "Alice", "password": "secret"})
        login_resp = self.receive_response()
        self.assertEqual(login_resp["status"], "ok", "❌ Alice should log in successfully.")

        # Alice sends message to Bob
        self.send_message("send_message", {"sender": "Alice", "recipient": "Bob", "content": "Hello Bob!"})
        msg_response = self.receive_response()
        self.assertEqual(msg_response["status"], "ok", "❌ Should store the message from Alice to Bob.")

        # Delete Alice's account
        self.send_message("delete_account", {})
        del_response = self.receive_response()
        print(del_response)
        self.assertEqual(del_response["status"], "ok", "❌ Deleting account should succeed.")
        self.assertIn("has been deleted", del_response["msg"], "❌ Should confirm account deletion message.")

        # Attempt to log in again as Alice -> user should not exist
        self.send_message("login", {"username": "Alice", "password": "secret"})
        re_login_response = self.receive_response()
        self.assertEqual(re_login_response["status"], "error", "❌ Should fail - user no longer exists.")
        self.assertIn("not found", re_login_response["msg"], "❌ Should indicate 'Username not found.'")

        # Attempt to log in as Bob
        self.send_message("login", {"username": "Bob", "password": "bobpass"})
        bob_login_resp = self.receive_response()
        self.assertEqual(bob_login_resp["status"], "ok", "❌ Bob should still exist and be able to log in.")

        # Bob fetches messages -> Should find none from Alice, because her messages were deleted
        self.send_message("fetch_away_msgs", {"num_messages": 5})
        bob_fetch_resp = self.receive_response()
        self.assertEqual(bob_fetch_resp["status"], "ok", "❌ fetch_away_msgs should succeed for Bob.")
        self.assertEqual(len(bob_fetch_resp["msg"]), 0, "❌ All of Alice's messages should be removed.")


if __name__ == "__main__":
    import unittest
    unittest.main()
