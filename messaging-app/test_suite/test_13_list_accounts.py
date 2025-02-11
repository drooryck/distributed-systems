from test_base import BaseTest

class TestListAccounts(BaseTest):
    def test_list_accounts_basic(self):
        """Test listing accounts using a pattern"""
        self.reset_database()

        # Sign up some users
        self.send_message("signup", {"username": "alice123", "password": "pass"})
        self.receive_response()

        self.send_message("signup", {"username": "bob456", "password": "pass"})
        self.receive_response()

        self.send_message("signup", {"username": "charlie789", "password": "pass"})
        self.receive_response()

        # Search for "a" (should match "alice123" and "charlie789")
        self.send_message("list_accounts", {"pattern": "a", "start": 0, "count": 10})
        response = self.receive_response()

        self.assertEqual(response["data"]["status"], "ok")
        self.assertIn("alice123", response["data"]["users"])
        self.assertIn("charlie789", response["data"]["users"])
        self.assertNotIn("bob456", response["data"]["users"])

    def test_list_accounts_pagination(self):
        """Test that account listing supports pagination"""
        self.reset_database()

        # Sign up multiple users
        for i in range(15):
            self.send_message("signup", {"username": f"user{i}", "password": "pass"})
            self.receive_response()

        # Fetch first 5 users
        self.send_message("list_accounts", {"pattern": "user", "start": 0, "count": 5})
        response = self.receive_response()

        self.assertEqual(response["data"]["status"], "ok")
        self.assertEqual(len(response["data"]["users"]), 5)

        # Fetch next 5 users
        self.send_message("list_accounts", {"pattern": "user", "start": 5, "count": 5})
        response = self.receive_response()

        self.assertEqual(response["data"]["status"], "ok")
        self.assertEqual(len(response["data"]["users"]), 5)

    def test_list_accounts_no_match(self):
        """Test listing accounts with a pattern that doesn't match any user"""
        self.reset_database()

        # Sign up a few users
        self.send_message("signup", {"username": "alice", "password": "pass"})
        self.receive_response()
        self.send_message("signup", {"username": "bob", "password": "pass"})
        self.receive_response()

        # Search for a nonexistent pattern
        self.send_message("list_accounts", {"pattern": "zxy"})
        response = self.receive_response()

        self.assertEqual(response["data"]["status"], "ok")
        self.assertEqual(len(response["data"]["users"]), 0)  # Should return an empty list

    def test_list_accounts_no_pattern(self):
        """Test that listing accounts without a pattern returns an error"""
        self.reset_database()

        self.send_message("list_accounts", {})
        response = self.receive_response()

        self.assertEqual(response["data"]["status"], "error")
        self.assertEqual(response["data"]["msg"], "No pattern provided.")

if __name__ == "__main__":
    import unittest
    unittest.main()
