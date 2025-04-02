from test_base import BaseTest
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

class TestListAccounts(BaseTest):
    def test_list_accounts_basic(self):
        """Test listing accounts using a pattern"""
        stub = self.stub

        # Sign up users
        stub.Signup(chat_service_pb2.SignupRequest(username="alice123", password="pass"))
        login_resp = stub.Login(chat_service_pb2.LoginRequest(username="alice123", password="pass"))
        stub.Logout(chat_service_pb2.EmptyRequest(auth_token=login_resp.auth_token))

        stub.Signup(chat_service_pb2.SignupRequest(username="bob456", password="pass"))
        stub.Login(chat_service_pb2.LoginRequest(username="bob456", password="pass"))

        stub.Signup(chat_service_pb2.SignupRequest(username="charlie789", password="pass"))
        charlie_login = stub.Login(chat_service_pb2.LoginRequest(username="charlie789", password="pass"))

        # Search for "a" (should match "alice123" and "charlie789")
        list_response = stub.ListAccounts(
            chat_service_pb2.ListAccountsRequest(
                auth_token=charlie_login.auth_token,
                pattern="a",
                start=0,
                count=10
            )
        )

        self.assertEqual(list_response.status, "ok")
        usernames = {user.username for user in list_response.users}
        self.assertIn("alice123", usernames)
        self.assertIn("charlie789", usernames)
        self.assertNotIn("bob456", usernames)

    def test_list_accounts_pagination(self):
        """Test that account listing supports pagination"""
        stub = self.stub

        # Sign up multiple users
        last_login = None
        for i in range(15):
            stub.Signup(chat_service_pb2.SignupRequest(username=f"user{i}", password="pass"))
            last_login = stub.Login(chat_service_pb2.LoginRequest(username=f"user{i}", password="pass"))

        # Fetch first 5 users
        first_page = stub.ListAccounts(
            chat_service_pb2.ListAccountsRequest(
                auth_token=last_login.auth_token,
                pattern="user",
                start=0,
                count=5
            )
        )
        self.assertEqual(first_page.status, "ok")
        self.assertEqual(len(first_page.users), 5)

        # Fetch next 5 users
        second_page = stub.ListAccounts(
            chat_service_pb2.ListAccountsRequest(
                auth_token=last_login.auth_token,
                pattern="user",
                start=5,
                count=5
            )
        )
        self.assertEqual(second_page.status, "ok")
        self.assertEqual(len(second_page.users), 5)

    def test_list_accounts_no_match(self):
        """Test listing accounts with a pattern that doesn't match any user"""
        stub = self.stub

        # Sign up test users
        stub.Signup(chat_service_pb2.SignupRequest(username="alice", password="pass"))
        stub.Signup(chat_service_pb2.SignupRequest(username="bob", password="pass"))
        login_resp = stub.Login(chat_service_pb2.LoginRequest(username="bob", password="pass"))

        # Search for nonexistent pattern
        list_response = stub.ListAccounts(
            chat_service_pb2.ListAccountsRequest(
                auth_token=login_resp.auth_token,
                pattern="zxy",
                start=0,
                count=10
            )
        )
        self.assertEqual(list_response.status, "ok")
        self.assertEqual(len(list_response.users), 0)


if __name__ == "__main__":
    import unittest
    unittest.main()