import socket
import threading
import sqlite3
from queue import Queue
import json
import struct
import argparse
import struct

from protocol import Message, JSONProtocolHandler, CustomProtocolHandler


from database import Database
from actions import ActionHandler


#############################
# 1. SERVER CLASS
#############################

class Server:
    def __init__(self, host="10.250.120.214", port=5555, protocol="json", db_name="chat.db"):
        self.host = host
        self.port = port
        self.protocol = protocol.lower()
        self.protocol_handler = JSONProtocolHandler() if self.protocol == "json" else CustomProtocolHandler()

        self.db_name = db_name

        self.client_queues = {}     # {client_id: Queue()}
        self.logged_in_users = {}   # {client_id: username}
        self.server_lock = threading.Lock()

        self.db = Database(db_name)
        self.actions = ActionHandler(self.db, self.protocol_handler, self.logged_in_users)

    def start_server(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        print(f"Server listening on {self.host}:{self.port} (protocol={self.protocol})")

        try:
            while True:
                conn, addr = self.sock.accept()
                client_id = addr
                self.client_queues[client_id] = Queue()
                thread = threading.Thread(target=self.handle_client, args=(conn, client_id))
                thread.start()
        except KeyboardInterrupt:
            print("Shutting down server...")
        finally:
            self.sock.close()

    def handle_client(self, conn, client_id):
        print(f"[+] Client connected: {client_id}")
        try:
            while True:
                message = self.protocol_handler.receive(conn)
                print('server gets', message)
                if not message:
                    print(f"[-] Client disconnected: {client_id}")
                    break
                self.client_queues[client_id].put(message)
                self.process_job_queue(client_id, conn)
        except Exception as e:
            print(f"Error handling {client_id}: {e}")
        finally:
            conn.close()
            if client_id in self.client_queues:
                del self.client_queues[client_id]
            if client_id in self.logged_in_users:
                del self.logged_in_users[client_id]

    def process_job_queue(self, client_id, conn):
        queue = self.client_queues[client_id]
        while not queue.empty():
            job = queue.get()
            self.actions.process_client_action(client_id, job, conn)

    #############################
    # UTILITIES
    #############################

    def _store_message(self, sender, recipient, content):
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO messages (sender, recipient, content, to_deliver)
            VALUES (?, ?, ?, ?)
        """, (sender, recipient, content, 0))
        self.conn.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the messaging server.")
    parser.add_argument("--host", type=str, default="10.250.120.214", help="IP address to bind the server (default: 10.250.120.214)")
    parser.add_argument("--port", type=int, default=5555, help="Port to listen on (default: 5555)")
    parser.add_argument("--protocol", type=str, choices=["json", "custom"], default="json", help="Protocol to use (default: json)")
    # add reset database keyword with default no as an argument
    args = parser.parse_args()

    server = Server(host=args.host, port=args.port, protocol=args.protocol)
    server.start_server()

