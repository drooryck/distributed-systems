#!/usr/bin/env python3
"""
Integration test file that measures gRPC request/response sizes for all 11 RPC methods
defined in chat_service.proto. Place this file under your 'integration_tests/' folder
and run it after your server is up (e.g., 'python -m unittest integration_tests.test_integration_grpc_sizes').
"""

import unittest
import grpc
import sys
import os

# Adjust Python path to import generated code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chat_service_pb2
import chat_service_pb2_grpc

###############################################################################
# Interceptor to measure request/response sizes
###############################################################################
class SizeMeasuringInterceptor(grpc.UnaryUnaryClientInterceptor):
    """
    Intercepts unary-unary RPC calls on the client side to measure the
    serialized request/response sizes in bytes.
    This version forcefully calls SerializeToString() on the response.
    """

    def __init__(self):
        self.measurements = []  # Will store each measurement as a dict

    def intercept_unary_unary(self, continuation, client_call_details, request):
        # Serialize request
        request_bytes = request.SerializeToString()
        req_size = len(request_bytes)

        # Proceed with the RPC: Get the outcome (which is a _UnaryOutcome)
        outcome = continuation(client_call_details, request)

        # Extract the actual response using result() if available.
        try:
            response = outcome.result()
        except Exception as e:
            print(f"[FORCED SerializeToString ERROR] Unable to extract result: {e}")
            response = outcome

        # Forcefully attempt to call SerializeToString() on the response
        try:
            forced_bytes = response.SerializeToString()
            resp_size = len(forced_bytes)
        except Exception as e:
            print(f"[FORCED SerializeToString ERROR] type(response)={type(response)}, error={e}")
            resp_size = 0

        # Determine which RPC method is being called
        method_name = client_call_details.method.split("/")[-1]

        # Store res
        self.measurements.append({
            "method": method_name,
            "request_size": req_size,
            "response_size": resp_size
        })

        return outcome

###############################################################################
# Integration test suite covering all 11 RPC methods
###############################################################################
class TestGrpcMessageSizes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Create an insecure channel with SizeMeasuringInterceptor attached.
        For best accuracy, disable compression on both client & server.
        """
        cls.size_interceptor = SizeMeasuringInterceptor()

        # Create channel with interceptor
        cls.channel = grpc.intercept_channel(
            grpc.insecure_channel(
                "127.0.0.1:50051"
            ),
            cls.size_interceptor
        )
        cls.stub = chat_service_pb2_grpc.ChatServiceStub(cls.channel)

        # Optionally, do a ResetDB so we start with a clean database:
        # (Uncomment if desired)
        # cls.stub.ResetDB(chat_service_pb2.EmptyRequest(auth_token="ADMIN_TOKEN"))

    def test_01_signup(self):
        """(1) signup"""
        request = chat_service_pb2.SignupRequest(username="size_test_user", password="fake_hash")
        response = self.stub.Signup(request)
        self.assertIn(response.status, ["ok", "error"])

    def test_02_login(self):
        """(2) login"""
        request = chat_service_pb2.LoginRequest(username="size_test_user", password="fake_hash")
        response = self.stub.Login(request)
        self.assertTrue(response.status)

    def test_03_logout(self):
        """(3) logout"""
        request = chat_service_pb2.EmptyRequest(auth_token="FAKE_TOKEN_123")
        response = self.stub.Logout(request)
        self.assertTrue(response.status)

    def test_04_count_unread(self):
        """(4) count_unread"""
        request = chat_service_pb2.CountUnreadRequest(auth_token="FAKE_TOKEN_123")
        response = self.stub.CountUnread(request)
        self.assertTrue(response.status)

    def test_05_send_message(self):
        """(5) send_message"""
        request = chat_service_pb2.SendMessageRequest(
            auth_token="FAKE_TOKEN_123",
            recipient="someone_else",
            content="Hello from gRPC size test!"
        )
        response = self.stub.SendMessage(request)
        self.assertTrue(response.status)

    def test_06_list_messages(self):
        """(6) list_messages (send_messages_to_client)"""
        request = chat_service_pb2.ListMessagesRequest(
            auth_token="FAKE_TOKEN_123",
            start=0,
            count=5
        )
        response = self.stub.ListMessages(request)
        self.assertIn(response.status, ["ok", "error"])

    def test_07_fetch_away_msgs(self):
        """(7) fetch_away_msgs"""
        request = chat_service_pb2.FetchAwayMsgsRequest(auth_token="FAKE_TOKEN_123", limit=5)
        response = self.stub.FetchAwayMsgs(request)
        self.assertIn(response.status, ["ok", "error"])

    def test_08_list_accounts(self):
        """(8) list_accounts"""
        request = chat_service_pb2.ListAccountsRequest(
            auth_token="FAKE_TOKEN_123",
            pattern="size_test",
            start=0,
            count=10
        )
        response = self.stub.ListAccounts(request)
        self.assertIn(response.status, ["ok", "error"])

    def test_09_delete_messages(self):
        """(9) delete_messages"""
        request = chat_service_pb2.DeleteMessagesRequest(
            auth_token="FAKE_TOKEN_123",
            message_ids_to_delete=[123, 124]
        )
        response = self.stub.DeleteMessages(request)
        self.assertIn(response.status, ["ok", "error"])

    def test_10_delete_account(self):
        """(10) delete_account"""
        request = chat_service_pb2.EmptyRequest(auth_token="FAKE_TOKEN_123")
        response = self.stub.DeleteAccount(request)
        self.assertIn(response.status, ["ok", "error"])

    def test_11_reset_db(self):
        """(11) reset_db"""
        request = chat_service_pb2.EmptyRequest(auth_token="FAKE_TOKEN_123")
        response = self.stub.ResetDB(request)
        self.assertIn(response.status, ["ok", "error"])

    @classmethod
    def tearDownClass(cls):
        """
        Print out all measurement data after the tests finish.
        """
        print("\n=== gRPC Size Measurements (All 11 Methods) ===")
        for record in cls.size_interceptor.measurements:
            print(
                f"Method: {record['method']:<20} "
                f"Request bytes: {record['request_size']:<4} "
                f"Response bytes: {record['response_size']:<4}"
            )

        cls.channel.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
