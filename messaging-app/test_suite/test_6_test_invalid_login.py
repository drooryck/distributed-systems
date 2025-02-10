from test_base import BaseTest

class TestInvalidLogin(BaseTest):
    def test_invalid_login(self):
        """Test that invalid login attempts fail correctly"""
        self.reset_database()

        ### 1️⃣ Sign up a valid user ###
        self.send_message("signup", {"username": "Alice", "password": "correct_password"})
        self.receive_response()

        ### 2️⃣ Attempt login with wrong password ###
        self.send_message("login", {"username": "Alice", "password": "wrong_password"})
        response = self.receive_response()
        self.assertEqual(response["data"]["status"], "error", "❌ Test Failed: Logged in with wrong password!")
        print("✅ Test Passed: Cannot log in with the wrong password.")

        ### 3️⃣ Attempt login with missing password ###
        self.send_message("login", {"username": "Alice"})
        response = self.receive_response()
        self.assertEqual(response["data"]["status"], "error", "❌ Test Failed: Logged in without a password!")
        print("✅ Test Passed: Cannot log in without a password.")

        ### 4️⃣ Attempt login with missing username ###
        self.send_message("login", {"password": "correct_password"})
        response = self.receive_response()
        self.assertEqual(response["data"]["status"], "error", "❌ Test Failed: Logged in without a username!")
        print("✅ Test Passed: Cannot log in without a username.")

        ### 5️⃣ Attempt login with an unregistered username ###
        self.send_message("login", {"username": "GhostUser", "password": "password123"})
        response = self.receive_response()
        self.assertEqual(response["data"]["status"], "error", "❌ Test Failed: Logged in with a non-existent user!")
        print("✅ Test Passed: Cannot log in with an unregistered user.")

if __name__ == "__main__":
    import unittest
    unittest.main()
