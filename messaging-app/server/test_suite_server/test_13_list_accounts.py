from test_base import BaseTest

class TestListAccounts(BaseTest):
    def test_list_accounts_basic(self):
        """Test listing accounts using a pattern"""
        self.reset_database()

        # recall we need to always do 'receive response' after sending a message or the socket buffer will have stale data.

        # Sign up some users
        self.send_message("signup", {"username": "alice123", "password": "pass"}, is_response=0)
        response = self.receive_response()
        self.send_message("login", {"username": "alice123", "password": "pass"}, is_response=0)
        response = self.receive_response()
        self.send_message("logout", {}, is_response=0)
        self.receive_response()

        self.send_message("signup", {"username": "bob456", "password": "pass"}, is_response=0)
        response = self.receive_response()
        self.send_message("login", {"username": "bob456", "password": "pass"}, is_response=0)
        self.receive_response()

        self.send_message("signup", {"username": "charlie789", "password": "pass"}, is_response=0)
        response = self.receive_response()
        self.send_message("login", {"username": "charlie789", "password": "pass"}, is_response=0)
        self.receive_response()

        self.time.sleep(0.1)

        # Search for "a" (should match "alice123" and "charlie789")
        self.send_message("list_accounts", {"pattern": "a", "start": 0, "count": 10}, is_response=0)
        response = self.receive_response()
        print('received response:', response)
        print("#####")

        self.assertEqual(response["status"], "ok")

        # Ensure response["users"] contains tuples of (id, username)
        usernames = {username for _, username in response["users"]}

        self.assertIn("alice123", usernames)
        self.assertIn("charlie789", usernames)
        self.assertNotIn("bob456", usernames)

    def test_list_accounts_pagination(self):
        """Test that account listing supports pagination"""
        self.reset_database()

        # Sign up multiple users
        for i in range(15):
            self.send_message("signup", {"username": f"user{i}", "password": "pass"}, is_response=0)
            resp = self.receive_response()

        # Fetch first 5 users
        self.send_message("list_accounts", {"pattern": "user", "start": 0, "count": 5}, is_response=0)
        response = self.receive_response()
        print('response was', response)

        self.assertEqual(response["status"], "ok")
        self.assertEqual(len(response["users"]), 5)

        # Fetch next 5 users
        self.send_message("list_accounts", {"pattern": "user", "start": 5, "count": 5}, is_response=0)
        response = self.receive_response()

        self.assertEqual(response["status"], "ok")
        self.assertEqual(len(response["users"]), 5)

    def test_list_accounts_no_match(self):
        """Test listing accounts with a pattern that doesn't match any user"""
        self.reset_database()

        # Sign up a few users
        self.send_message("signup", {"username": "alice", "password": "pass"}, is_response=0)
        response = self.receive_response()
        self.send_message("signup", {"username": "alice", "password": "pass"}, is_response=0)
        self.receive_response()
        self.send_message("signup", {"username": "bob", "password": "pass"}, is_response=0)
        response = self.receive_response()
        self.send_message("signup", {"username": "bob", "password": "pass"}, is_response=0)
        self.receive_response()

        # Search for a nonexistent pattern
        self.send_message("list_accounts", {"pattern": "zxy"}, is_response=0)
        response = self.receive_response()
        self.send_message("list_accounts", {"pattern": "zxy"}, is_response=0)
        response = self.receive_response()

        self.assertEqual(response["status"], "ok")
        self.assertEqual(len(response["users"]), 0)  # Should return an empty list

    def test_list_accounts_no_pattern(self):
        """Test that listing accounts without a pattern returns an error"""
        self.reset_database()

        self.send_message("list_accounts", {}, is_response=0)
        response = self.receive_response()
        self.send_message("list_accounts", {}, is_response=0)
        response = self.receive_response()

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["msg"], "No pattern provided.")

if __name__ == "__main__":
    import unittest
    unittest.main()