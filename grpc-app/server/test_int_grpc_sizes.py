#!/usr/bin/env python3
"""
Integration test file that measures both gRPC protobuf payload sizes (per RPC)
and full bytes (including HTTP/2 framing, headers, etc.) passed over the wire,
via a simple TCP proxy. This version provides a per-RPC breakdown of full bytes.
"""

import unittest
import grpc
import sys
import os
import threading
import socket
import socketserver

# Adjust Python path to import generated code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import chat_service_pb2
import chat_service_pb2_grpc

###############################################################################
# TCP Proxy to capture full integration test bytes
###############################################################################
class TCPProxyHandler(socketserver.BaseRequestHandler):
    def handle(self):
        # Connect to the actual server.
        remote_socket = socket.create_connection(
            (self.server.remote_host, self.server.remote_port)
        )
        # Start two threads to handle bidirectional data transfer.
        threads = []
        threads.append(threading.Thread(target=self.forward, args=(self.request, remote_socket, 'cs')))
        threads.append(threading.Thread(target=self.forward, args=(remote_socket, self.request, 'sc')))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        remote_socket.close()

    def forward(self, source, destination, direction):
        try:
            while True:
                data = source.recv(4096)
                if not data:
                    break
                destination.sendall(data)
                # Update the proxy's byte counters.
                if direction == 'cs':
                    self.server.total_client_to_server += len(data)
                else:
                    self.server.total_server_to_client += len(data)
        except Exception:
            # Ignore exceptions for simplicity.
            pass

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    def __init__(self, server_address, RequestHandlerClass, remote_host, remote_port):
        super().__init__(server_address, RequestHandlerClass)
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.total_client_to_server = 0  # Total bytes from client to server.
        self.total_server_to_client = 0  # Total bytes from server to client.

class TCPProxy:
    def __init__(self, listen_host, listen_port, remote_host, remote_port):
        self.server = ThreadedTCPServer(
            (listen_host, listen_port), TCPProxyHandler, remote_host, remote_port
        )
        self.thread = threading.Thread(target=self.server.serve_forever)
    def start(self):
        self.thread.start()
    def stop(self):
        self.server.shutdown()
        self.thread.join()
    def get_totals(self):
        return (self.server.total_client_to_server, self.server.total_server_to_client)
    def reset_totals(self):
        # Reset the counters to zero.
        self.server.total_client_to_server = 0
        self.server.total_server_to_client = 0

###############################################################################
# Interceptor to measure protobuf request/response sizes
###############################################################################
class SizeMeasuringInterceptor(grpc.UnaryUnaryClientInterceptor):
    """
    Intercepts unary-unary RPC calls on the client side to measure the
    serialized request/response sizes in bytes (protobuf payload only).
    """
    def __init__(self):
        self.measurements = []  # Each measurement is stored as a dict

    def intercept_unary_unary(self, continuation, client_call_details, request):
        # Measure serialized request size.
        request_bytes = request.SerializeToString()
        req_size = len(request_bytes)

        # Proceed with the RPC call.
        outcome = continuation(client_call_details, request)
        try:
            response = outcome.result()
        except Exception as e:
            print(f"[ERROR] Unable to extract result: {e}")
            response = outcome

        # Measure serialized response size.
        try:
            forced_bytes = response.SerializeToString()
            resp_size = len(forced_bytes)
        except Exception as e:
            print(f"[ERROR] type(response)={type(response)}, error={e}")
            resp_size = 0

        method_name = client_call_details.method.split("/")[-1]
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
        Start the TCP proxy and create a gRPC channel (via the proxy) with
        the SizeMeasuringInterceptor attached.
        """
        # Start TCP proxy: listen on port 50052 and forward to the actual server on 50051.
        cls.tcp_proxy = TCPProxy("127.0.0.1", 50052, "127.0.0.1", 50051)
        cls.tcp_proxy.start()

        # Set up client interceptor for protobuf measurements.
        cls.size_interceptor = SizeMeasuringInterceptor()
        # Create a gRPC channel to the proxy.
        cls.channel = grpc.intercept_channel(
            grpc.insecure_channel("127.0.0.1:50052"),
            cls.size_interceptor
        )
        cls.stub = chat_service_pb2_grpc.ChatServiceStub(cls.channel)
        # Prepare a list to store integration (full-wire) measurements per RPC.
        cls.integration_measurements = []

    def measure_integration_bytes(self, method_name, rpc_call):
        """
        Reset the TCP proxy counters, call the RPC, then record the bytes sent.
        """
        # Reset proxy counters.
        self.__class__.tcp_proxy.reset_totals()
        # Execute the RPC call.
        result = rpc_call()
        # Read the counters immediately after the call.
        cs_bytes, sc_bytes = self.__class__.tcp_proxy.get_totals()
        # Store per-RPC full byte measurements.
        self.__class__.integration_measurements.append({
            "method": method_name,
            "client_to_server": cs_bytes,
            "server_to_client": sc_bytes
        })
        return result

    def test_01_signup(self):
        request = chat_service_pb2.SignupRequest(username="size_test_user", password="fake_hash")
        response = self.measure_integration_bytes("Signup", lambda: self.stub.Signup(request))
        self.assertIn(response.status, ["ok", "error"])

    def test_02_login(self):
        request = chat_service_pb2.LoginRequest(username="size_test_user", password="fake_hash")
        response = self.measure_integration_bytes("Login", lambda: self.stub.Login(request))
        self.assertTrue(response.status)

    def test_03_logout(self):
        request = chat_service_pb2.EmptyRequest(auth_token="FAKE_TOKEN_123")
        response = self.measure_integration_bytes("Logout", lambda: self.stub.Logout(request))
        self.assertTrue(response.status)

    def test_04_count_unread(self):
        request = chat_service_pb2.CountUnreadRequest(auth_token="FAKE_TOKEN_123")
        response = self.measure_integration_bytes("CountUnread", lambda: self.stub.CountUnread(request))
        self.assertTrue(response.status)

    def test_05_send_message(self):
        request = chat_service_pb2.SendMessageRequest(
            auth_token="FAKE_TOKEN_123",
            recipient="someone_else",
            content="Hello from gRPC size test!"
        )
        response = self.measure_integration_bytes("SendMessage", lambda: self.stub.SendMessage(request))
        self.assertTrue(response.status)

    def test_06_list_messages(self):
        request = chat_service_pb2.ListMessagesRequest(
            auth_token="FAKE_TOKEN_123",
            start=0,
            count=5
        )
        response = self.measure_integration_bytes("ListMessages", lambda: self.stub.ListMessages(request))
        self.assertIn(response.status, ["ok", "error"])

    def test_07_fetch_away_msgs(self):
        request = chat_service_pb2.FetchAwayMsgsRequest(auth_token="FAKE_TOKEN_123", limit=5)
        response = self.measure_integration_bytes("FetchAwayMsgs", lambda: self.stub.FetchAwayMsgs(request))
        self.assertIn(response.status, ["ok", "error"])

    def test_08_list_accounts(self):
        request = chat_service_pb2.ListAccountsRequest(
            auth_token="FAKE_TOKEN_123",
            pattern="size_test",
            start=0,
            count=10
        )
        response = self.measure_integration_bytes("ListAccounts", lambda: self.stub.ListAccounts(request))
        self.assertIn(response.status, ["ok", "error"])

    def test_09_delete_messages(self):
        request = chat_service_pb2.DeleteMessagesRequest(
            auth_token="FAKE_TOKEN_123",
            message_ids_to_delete=[123, 124]
        )
        response = self.measure_integration_bytes("DeleteMessages", lambda: self.stub.DeleteMessages(request))
        self.assertIn(response.status, ["ok", "error"])

    def test_10_delete_account(self):
        request = chat_service_pb2.EmptyRequest(auth_token="FAKE_TOKEN_123")
        response = self.measure_integration_bytes("DeleteAccount", lambda: self.stub.DeleteAccount(request))
        self.assertIn(response.status, ["ok", "error"])

    def test_11_reset_db(self):
        request = chat_service_pb2.EmptyRequest(auth_token="FAKE_TOKEN_123")
        response = self.measure_integration_bytes("ResetDB", lambda: self.stub.ResetDB(request))
        self.assertIn(response.status, ["ok", "error"])

    @classmethod
    def tearDownClass(cls):
        print("\n=== gRPC Protobuf Payload Measurements (All 11 Methods) ===")
        for record in cls.size_interceptor.measurements:
            print(
                f"Method: {record['method']:<20} "
                f"Request bytes: {record['request_size']:<4} "
                f"Response bytes: {record['response_size']:<4}"
            )

        print("\n=== Full Integration Test Bytes Breakdown (per RPC) ===")
        for record in cls.integration_measurements:
            print(
                f"Method: {record['method']:<20} "
                f"Client->Server: {record['client_to_server']:<4} "
                f"Server->Client: {record['server_to_client']:<4}"
            )

        # Print overall totals from integration measurements.
        total_cs = sum(r["client_to_server"] for r in cls.integration_measurements)
        total_sc = sum(r["server_to_client"] for r in cls.integration_measurements)
        print("\n=== Overall Full Integration Test Bytes (via TCP Proxy) ===")
        print(f"Total client->server bytes: {total_cs}")
        print(f"Total server->client bytes: {total_sc}")

        cls.tcp_proxy.stop()
        cls.channel.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
