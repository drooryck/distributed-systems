import unittest
import chat_service_pb2
from test_base import BaseTest

class TestSendMessagesToClient(BaseTest):
    def test_send_messages_to_client(self):
        """
        1. Alice & Bob sign up
        2. Alice sends a message to Bob
        3. Bob logs in & fetches messages -> message is now delivered
        4. Bob calls ListMessages to see delivered messages
        5. Verify Bob receives the correct delivered messages
        """
        stub = self.stub  # Get gRPC stub

        # Sign up Alice and Bob
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))
        stub.Signup(chat_service_pb2.SignupRequest(username="Bob", password="bobpass"))

        # Login Alice
        alice_login = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        self.assertEqual(alice_login.status, "ok", "❌ Alice should log in successfully")
        alice_token = alice_login.auth_token

        # Alice sends a message to Bob
        send_response = stub.SendMessage(
            chat_service_pb2.SendMessageRequest(auth_token=alice_token, recipient="Bob", content="Hello Bob!")
        )
        self.assertEqual(send_response.status, "ok", "❌ Sending message should succeed")

        # Logout Alice
        stub.Logout(chat_service_pb2.EmptyRequest(auth_token=alice_token))

        # Bob logs in
        bob_login = stub.Login(chat_service_pb2.LoginRequest(username="Bob", password="bobpass"))
        self.assertEqual(bob_login.status, "ok", "❌ Bob should log in successfully")
        bob_token = bob_login.auth_token

        # Bob fetches pending messages (this marks them as delivered)
        fetch_response = stub.FetchAwayMsgs(chat_service_pb2.FetchAwayMsgsRequest(auth_token=bob_token, limit=5))
        self.assertEqual(fetch_response.status, "ok", "❌ FetchAwayMsgs should succeed")

        # Bob retrieves delivered messages via ListMessages
        list_response = stub.ListMessages(chat_service_pb2.ListMessagesRequest(auth_token=bob_token, start=0, count=10))
        self.assertEqual(list_response.status, "ok", "❌ ListMessages should succeed")
        self.assertEqual(len(list_response.messages), 1, "❌ Bob should see exactly 1 delivered message")
        self.assertEqual(list_response.messages[0].content, "Hello Bob!", "❌ The delivered message content should match")

if __name__ == "__main__":
    unittest.main()
