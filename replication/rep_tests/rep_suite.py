# rep_suite.py
import subprocess
import time
import signal
import os
import unittest
from test_persistence import TestPersistence
from test_rep_failover import TestReplicationFailover

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PATH = os.path.join(BASE_DIR, "server", "server.py")

PRIMARY_CMD = [
    "python", SERVER_PATH,
    "--port", "50051",
    "--db_file", "repl_primary.db",
    "--role", "primary",
    "--backups", "localhost:50052,localhost:50053"
]
BACKUP1_CMD = [
    "python", SERVER_PATH,
    "--port", "50052",
    "--db_file", "repl_backup1.db",
    "--role", "backup"
]
BACKUP2_CMD = [
    "python", SERVER_PATH,
    "--port", "50053",
    "--db_file", "repl_backup2.db",
    "--role", "backup"
]

def start_servers():
    print("🚀 Starting backup servers...")
    proc_b1 = subprocess.Popen(BACKUP1_CMD)
    proc_b2 = subprocess.Popen(BACKUP2_CMD)
    print("🚀 Starting primary server...")
    proc_primary = subprocess.Popen(PRIMARY_CMD)
    time.sleep(3)  # Allow time for servers to fully initialize
    return [proc_primary, proc_b1, proc_b2]

def stop_servers(procs):
    print("🛑 Stopping all servers...")
    for proc in procs:
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("⚠️ Timeout — force killing process.")
            proc.kill()
    print("✅ Servers shut down cleanly.")

if __name__ == "__main__":
    # Clean old DB files
    for db_file in ["repl_primary.db", "repl_backup1.db", "repl_backup2.db", "persistence_test.db"]:
        if os.path.exists(db_file):
            os.remove(db_file)

    # Start servers
    procs = start_servers()

    try:
        print("🧪 Running replication test suite...\n")
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.TestSuite([
                unittest.defaultTestLoader.loadTestsFromTestCase(TestPersistence),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestReplicationFailover)
            ])
        )
    finally:
        stop_servers(procs)