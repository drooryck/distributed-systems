from test_base import BaseTest
import chat_service_pb2

class TestMessageDeliveryStatus(BaseTest):
    def test_message_delivery(self):
        """Test that messages are marked as delivered once fetched"""

        stub = self.stub  # Get gRPC stub

        # Sign up Frank and Alice
        stub.Signup(chat_service_pb2.SignupRequest(username="Frank", password="pass123"))
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))

        # Alice logs in
        alice_login = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        self.assertEqual(alice_login.status, "ok")
        alice_token = alice_login.auth_token

        # Alice sends a message to Frank
        stub.SendMessage(
            chat_service_pb2.SendMessageRequest(auth_token=alice_token, recipient="Frank", content="Hello Frank!")
        )

        # Alice logs out
        stub.Logout(chat_service_pb2.EmptyRequest(auth_token=alice_token))

        # Frank logs in
        frank_login = stub.Login(chat_service_pb2.LoginRequest(username="Frank", password="pass123"))
        self.assertEqual(frank_login.status, "ok")
        frank_token = frank_login.auth_token

        # Step 1: Frank fetches messages (this marks them as delivered)
        fetch_response = stub.FetchAwayMsgs(
            chat_service_pb2.FetchAwayMsgsRequest(auth_token=frank_token, limit=5)
        )
        self.assertEqual(fetch_response.status, "ok")

        # Step 2: Frank lists messages (now they should be marked as delivered)
        list_response = stub.ListMessages(
            chat_service_pb2.ListMessagesRequest(auth_token=frank_token, start=0, count=10)
        )

        # ✅ Verify that Frank has received exactly 1 message
        self.assertEqual(len(list_response.messages), 1, "❌ Frank should see exactly 1 delivered message.")

        # ✅ Verify the message content
        self.assertEqual(list_response.messages[0].sender, "Alice", "❌ Message should be from Alice.")
        self.assertEqual(list_response.messages[0].content, "Hello Frank!", "❌ Message content is incorrect.")

if __name__ == "__main__":
    import unittest
    unittest.main()
