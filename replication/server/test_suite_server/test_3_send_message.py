from test_base import BaseTest
from protocol import chat_service_pb2
from protocol import chat_service_pb2_grpc

class TestSendMessage(BaseTest):
    def test_send_message(self):
        """Test that messages can be sent successfully"""

        stub = self.stub  # Get gRPC stub

        # Sign up Alice and Bob
        stub.Signup(chat_service_pb2.SignupRequest(username="Alice", password="secret"))
        stub.Signup(chat_service_pb2.SignupRequest(username="Bob", password="password"))

        # Alice logs in
        login_response = stub.Login(chat_service_pb2.LoginRequest(username="Alice", password="secret"))
        self.assertEqual(login_response.status, "ok")
        alice_token = login_response.auth_token

        # Alice sends a message to Bob
        send_response = stub.SendMessage(
            chat_service_pb2.SendMessageRequest(auth_token=alice_token, recipient="Bob", content="Hello Bob!")
        )
        self.assertEqual(send_response.status, "ok")

if __name__ == "__main__":
    import unittest
    unittest.main()
