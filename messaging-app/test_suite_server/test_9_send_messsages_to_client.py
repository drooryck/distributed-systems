from test_base import BaseTest

class TestSendMessagesToClient(BaseTest):
    def test_send_messages_to_client(self):
        """
        1. Alice & Bob sign up
        2. Alice sends a message to Bob
        3. Bob logs in & fetches messages -> message is now delivered
        4. Bob calls send_messages_to_client to see delivered messages and messages while logged in
        5. Verify Bob receives the correct delivered messages
        """
        self.reset_database()

        # Sign up Alice
        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        # Sign up Bob
        self.send_message("signup", {"username": "Bob", "password": "bobpass"})
        self.receive_response()

        # Login Alice
        self.send_message("login", {"username": "Alice", "password": "secret"})
        self.receive_response()

        # Alice sends a message to Bob
        self.send_message("send_message", {"sender": "Alice", "recipient": "Bob", "content": "Hello Bob!"})
        send_response = self.receive_response()
        self.assertEqual(send_response["status"], "ok", "❌ Sending message should succeed")
    

        # Logout Alice
        self.send_message("logout", {})
        self.receive_response()

        # Bob logs in
        self.send_message("login", {"username": "Bob", "password": "bobpass"})
        login_response = self.receive_response()
        self.assertEqual(login_response["status"], "ok", "❌ Bob should log in successfully")

        # Bob fetches messages -> they become delivered
        self.send_message("fetch_away_msgs", {"num_messages": 5})
        fetch_response = self.receive_response()
        
        self.assertEqual(fetch_response["status"], "ok", "❌ fetch__away_msgs should succeed")
        self.assertEqual(len(fetch_response["msg"]), 1, "❌ Bob should fetch exactly 1 new message")

        # Now Bob calls send_delivered_messages
        self.send_message("send_messages_to_client", {})
        delivered_response = self.receive_response()
        print(delivered_response)
    
        self.assertEqual(delivered_response["status"], "ok", "❌ send_messages_to_client should succeed")
        delivered_msgs = delivered_response["msg"]
        print(delivered_msgs)

        self.assertEqual(len(delivered_msgs), 1, "❌ Bob should see exactly 1 delivered message")
        self.assertEqual(delivered_msgs[0]["content"], "Hello Bob!", "❌ The delivered message content should match")

if __name__ == "__main__":
    import unittest
    unittest.main()
