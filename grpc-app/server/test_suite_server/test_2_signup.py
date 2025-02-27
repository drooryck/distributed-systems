from test_base import BaseTest
import chat_service_pb2

class TestSignup(BaseTest):
    def test_multiple_signups(self):
        """Test that multiple accounts can be created"""
        stub = self.stub

        # Sign up Charlie
        response1 = stub.Signup(chat_service_pb2.SignupRequest(username="Charlie", password="abc123"))
        self.assertEqual(response1.status, "ok")

        # Sign up Dave
        response2 = stub.Signup(chat_service_pb2.SignupRequest(username="Dave", password="xyz789"))
        self.assertEqual(response2.status, "ok")

if __name__ == "__main__":
    import unittest
    unittest.main()
