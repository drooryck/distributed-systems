from test_base import BaseTest

class TestInvalidLogin(BaseTest):
    def test_login_wrong_password(self):
        """
        1. Reset DB
        2. Signup a valid user
        3. Attempt login with the wrong password
        4. Expect an error response (not a disconnect)
        """
        self.reset_database()

        # Sign up a valid user: "Alice"
        self.send_message("signup", {"username": "Alice", "password": "correct_password"}, is_response=0)
        self.receive_response()  # consume signup response

        # Attempt login with the wrong password
        self.send_message("login", {"username": "Alice", "password": "wrong_password"}, is_response=0)
        response = self.receive_response()

        # Validate
        self.assertIsNotNone(response, "❌ Did not receive a response for wrong password!")
        self.assertEqual(response["status"], "error", "❌ Test Failed: Logged in with wrong password!")
        print("✅ test_login_wrong_password: Cannot log in with the wrong password.")

    def test_login_missing_password(self):
        """
        1. Reset DB
        2. Signup a valid user
        3. Send login request missing 'password'
        4. Expect the server to disconnect (receive_response() -> None).
        """
        self.reset_database()

        # Sign up a valid user: "Alice"
        self.send_message("signup", {"username": "Alice", "password": "correct_password"}, is_response=0)
        self.receive_response()  # consume signup response

        # Attempt login with missing password
        self.send_message("login", {"username": "Alice"}, is_response=0)
        response = self.receive_response()

        # Validate
        self.assertIsNone(response, "❌ Test Failed: Server did not disconnect on missing password.")
        print("✅ test_login_missing_password: Server disconnects on missing password.")

    def test_login_missing_username(self):
        """
        1. Reset DB
        2. Signup a valid user
        3. Send login request missing 'username'
        4. Expect the server to disconnect (ConnectionResetError).
        """
        self.reset_database()

        # Sign up a valid user: "Alice"
        self.send_message("signup", {"username": "Alice", "password": "correct_password"}, is_response=0)
        self.receive_response()  # Consume signup response

        # Attempt login with missing username
        self.send_message("login", {"password": "correct_password"}, is_response=0)

        try:
            response = self.receive_response()
            self.fail("❌ Test Failed: Server did NOT disconnect on missing username.")  # This should never be reached
        except ConnectionResetError:
            print("✅ test_login_missing_username: Server disconnected as expected.")

    def test_login_non_existent_user(self):
        """
        1. Reset DB
        2. (Optional) You could sign up some other user, 
           but we intentionally do not sign up 'GhostUser'
        3. Attempt login with a non-existent user
        4. Expect an error response (not a disconnect)
        """
        self.reset_database()

        # (Optional) Sign up some other user if desired
        # self.send_message("signup", {"username": "Bob", "password": "some_password"})
        # self.receive_response()

        # Attempt login with an unregistered username
        self.send_message("login", {"username": "GhostUser", "password": "password123"}, is_response=0)
        response = self.receive_response()

        # Validate
        self.assertIsNotNone(response, "❌ Did not receive a response for non-existent user!")
        self.assertEqual(response["status"], "error", "❌ Test Failed: Logged in with a non-existent user!")
        print("✅ test_login_non_existent_user: Cannot log in with an unregistered user.")

if __name__ == "__main__":
    import unittest
    unittest.main()
