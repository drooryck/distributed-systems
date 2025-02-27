import unittest
import chat_service_pb2
from test_base import BaseTest

class TestDeleteAccount(BaseTest):
    def test_cannot_delete_without_login(self):
        """Ensure that trying to delete an account while not logged in returns an error."""

        stub = self.stub  # Get gRPC stub

        # Attempt to delete account without logging in
        response = stub.DeleteAccount(chat_service_pb2.EmptyRequest(auth_token="invalid_token"))

        # Validate
        self.assertEqual(response.status, "error", "❌ Should fail if no user is logged in.")
        self.assertIn("not logged in", response.msg.lower(), "❌ Error message should indicate no login.")

    def test_delete_account_removes_user_and_messages(self):
        """Ensure that deleting an account removes the user and all associated messages."""

        stub = self.stub  # Get gRPC stub

        # Sign up Bob
        stub.Signup(chat_service_pb2.SignupRequest(username="Bob", password="bobpass"))

        # Sign up Alice
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))

        # Alice logs in
        alice_login = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        self.assertEqual(alice_login.status, "ok", "❌ Alice should log in successfully.")
        alice_token = alice_login.auth_token

        # Bob logs in
        bob_login = stub.Login(chat_service_pb2.LoginRequest(username="Bob", password="bobpass"))
        self.assertEqual(bob_login.status, "ok", "❌ Bob should log in successfully.")
        bob_token = bob_login.auth_token

        # Alice sends a message to Bob
        send_response = stub.SendMessage(
            chat_service_pb2.SendMessageRequest(auth_token=alice_token, recipient="Bob", content="Hello Bob!")
        )
        self.assertEqual(send_response.status, "ok", "❌ Should store the message from Alice to Bob.")

        # Alice deletes her account
        del_response = stub.DeleteAccount(chat_service_pb2.EmptyRequest(auth_token=alice_token))
        print(del_response)
        self.assertEqual(del_response.status, "ok", "❌ Deleting account should succeed.")
        self.assertIn("deleted", del_response.msg.lower(), "❌ Should confirm account deletion message.")


        # Bob fetches messages -> Should find none from Alice, because her messages were deleted
        list_messages_response = stub.ListMessages(
            chat_service_pb2.ListMessagesRequest(auth_token=bob_token, start=0, count=10)
        )
        self.assertEqual(list_messages_response.status, "ok", "❌ ListMessages should succeed for Bob.")
        self.assertEqual(len(list_messages_response.messages), 0, "❌ All of Alice's messages should be removed.")

if __name__ == "__main__":
    unittest.main()
