from test_base import BaseTest

class TestDeleteSingleMessage(BaseTest):
    def test_delete_one_message(self):
        """
        1. Alice & Bob sign up
        2. Alice sends a message to Bob
        3. Bob logs in & fetches (delivers) the message
        4. Bob deletes that single message
        5. Confirm it's removed from send_messages_to_client
        """
        self.reset_database()

        # Sign up users
        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("signup", {"username": "Bob", "password": "bobpass"})
        self.receive_response()

        # Alice logs in & sends a message to Bob
        self.send_message("login", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("send_message", {"sender": "Alice", "recipient": "Bob", "content": "Hi Bob!"})
        self.receive_response()

        # Alice logs out
        self.send_message("logout", {})
        self.receive_response()

        # Bob logs in
        self.send_message("login", {"username": "Bob", "password": "bobpass"})
        self.receive_response()

        # Bob fetches -> message now delivered
        self.send_message("fetch_away_msgs", {"num_messages": 5})
        fetch_response = self.receive_response()
        self.assertEqual(len(fetch_response["data"]["msg"]), 1, "❌ Bob should fetch 1 message")

        msg_id = fetch_response["data"]["msg"][0]["id"]

        # Bob calls send_messages_to_client -> should see 1 message
        self.send_message("send_messages_to_client", {})
        delivered_before_delete = self.receive_response()
        self.assertEqual(len(delivered_before_delete["data"]["msg"]), 1, "❌ Should have 1 delivered message")

        # Bob deletes this message
        self.send_message("delete_messages", {"message_ids_to_delete": [msg_id]})
        delete_response = self.receive_response()
        self.assertEqual(delete_response["data"]["status"], "ok", "❌ Deleting single message should succeed")
        self.assertEqual(delete_response["data"]["deleted_count"], 1, "❌ Should delete exactly 1 message")

        # Verify it's no longer in delivered
        self.send_message("send_messages_to_client", {})
        delivered_after_delete = self.receive_response()
        self.assertEqual(len(delivered_after_delete["data"]["msg"]), 0, "❌ Message should be gone after deletion")

if __name__ == "__main__":
    import unittest
    unittest.main()
