from test_base import BaseTest

class TestDeleteMultipleMessages(BaseTest):
    def test_delete_multiple_messages(self):
        """
        1. Alice & Bob sign up
        2. Alice sends multiple messages to Bob
        3. Bob logs in & fetches -> messages now delivered
        4. Bob deletes all or some of those messages
        5. Confirm the deleted ones are no longer in send_delivered_messages
        """
        self.reset_database()

        # Sign up users
        self.send_message("signup", {"username": "Alice", "password": "secret"})
        self.receive_response()

        self.send_message("signup", {"username": "Bob", "password": "bobpass"})
        self.receive_response()

        # Alice logs in & sends multiple messages to Bob
        self.send_message("login", {"username": "Alice", "password": "secret"})
        self.receive_response()

        messages_to_send = ["Hi Bob!", "How are you?", "This is the 3rd message"]
        for content in messages_to_send:
            self.send_message("send_message", {"sender": "Alice", "recipient": "Bob", "content": content})
            self.receive_response()

        self.send_message("logout", {})
        self.receive_response()

        # Bob logs in
        self.send_message("login", {"username": "Bob", "password": "bobpass"})
        self.receive_response()

        # Bob fetches -> messages now delivered
        self.send_message("fetch_away_msgs", {"num_messages": 10})
        fetch_response = self.receive_response()
        delivered_list = fetch_response["data"]["messages"]
        self.assertEqual(len(delivered_list), 3, "❌ Bob should have 3 delivered messages")

        # Bob calls send_messages_to_client -> should see 3 messages
        self.send_message("send_messages_to_client", {})
        delivered_response = self.receive_response()
        self.assertEqual(len(delivered_response["data"]["messages"]), 3, "❌ Still expecting 3 delivered messages")

        # Delete 2 of them
        msg_ids = [m["id"] for m in delivered_list[:2]]  # first 2 messages
        self.send_message("delete_messages", {"message_ids_to_delete": msg_ids})
        delete_resp = self.receive_response()
        self.assertEqual(delete_resp["data"]["deleted_count"], 2, "❌ Should delete exactly 2 messages")

        # Now only 1 delivered message should remain
        self.send_message("send_messages_to_client", {})
        final_delivered = self.receive_response()
        self.assertEqual(len(final_delivered["data"]["messages"]), 1, "❌ Only 1 message should remain after deleting 2")

if __name__ == "__main__":
    import unittest
    unittest.main()
