import os
import threading
import queue
import random
import time
import datetime

# gRPC imports
import grpc
from concurrent import futures

# Data analysis and plotting
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import logical_clock_pb2
import logical_clock_pb2_grpc

def analyze_logs(df, output_dir):
    """
    Analyze and plot event data from the simulation, saving plots in output_dir.
    """

    os.makedirs(output_dir, exist_ok=True)

    # Convert system_time to datetime for proper sorting
    if not pd.api.types.is_datetime64_any_dtype(df["system_time"]):
        df["system_time"] = pd.to_datetime(df["system_time"])
    df.sort_values(by="system_time", inplace=True)

    # --- DRIFT CALCULATION AND PLOT (NEW) ---
    # 1) Compute how many seconds have passed since the earliest event
    start_time = df["system_time"].min()
    df["real_time_seconds"] = (df["system_time"] - start_time).dt.total_seconds()

    # 2) Define drift: difference between logical_clock and real_time_seconds
    df["drift"] = df["logical_clock"] - df["real_time_seconds"]

    # 3) Plot drift over time
    plt.figure(figsize=(10,6))
    sns.lineplot(data=df, x="system_time", y="drift", hue="vm_id", marker="o")
    plt.title("Drift of Logical Clocks from System Time")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "drift_over_time.png"))
    plt.close()
    # --- END DRIFT CALCULATION ---

    # --- 1) Plot Logical Clock Over Time ---
    plt.figure(figsize=(10,6))
    sns.lineplot(data=df, x="system_time", y="logical_clock", hue="vm_id", marker="o")
    plt.title("Logical Clock over Time (by VM)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "logical_clock_over_time.png"))
    plt.close()

    # --- 2) Plot Queue Length Over Time ---
    plt.figure(figsize=(10,6))
    sns.lineplot(data=df, x="system_time", y="queue_len", hue="vm_id", marker="o")
    plt.title("Queue Length over Time (by VM)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "queue_length_over_time.png"))
    plt.close()

    # --- 3) Count of Event Types per VM ---
    event_counts = df.groupby(["vm_id", "event_type"]).size().reset_index(name="count")
    print("\nEvent counts by VM and Event Type:")
    print(event_counts)

    # Plot: event_type on x-axis, hue by vm_id
    plt.figure(figsize=(8,5))
    sns.countplot(data=df, x="event_type", hue="vm_id")
    plt.title("Distribution of Event Types by VM (Default Grouping)")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "event_type_distribution.png"))
    plt.close()

    # --- 4) Another distribution: group by vm_id on x-axis, hue by event_type
    plt.figure(figsize=(8,5))
    sns.countplot(data=df, x="vm_id", hue="event_type")
    plt.title("Distribution of Event Types by VM (Grouped by VM)")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "event_type_distribution_by_vm.png"))
    plt.close()

    print(f"Plots saved to '{output_dir}/'.\n")



class VirtualMachine(threading.Thread):
    def __init__(self, vm_id, peers, port):
        """
        vm_id: int - The global VM ID (0,1,2, etc.)
        peers: list of (host, port) for the other VMs
        port: int - the port to bind this VM's gRPC server
        """
        super().__init__()
        self.vm_id = vm_id
        self.clock_rate = random.randint(1, 6)
        self.logical_clock = 0
        
        self.msg_queue = queue.Queue()  # for incoming messages
        self.peers = peers  # (host, port) of other machines
        
        self.local_log = []  # store log events as dictionaries
        self.port = port
        self.stop_flag = False
        self._grpc_server = None

    def run(self):
        """
        Start the gRPC server in a daemon thread, then perform self.clock_rate instructions per second
        until stop_flag is set.
        """
        server_thread = threading.Thread(target=self.run_server, daemon=True)
        server_thread.start()

        while not self.stop_flag:
            start_time = time.time()
            
            for _ in range(self.clock_rate):
                self.one_cycle()
                if self.stop_flag:
                    break
            
            elapsed = time.time() - start_time
            to_sleep = 1.0 - elapsed
            if to_sleep > 0:
                time.sleep(to_sleep)

    def one_cycle(self):
        if not self.msg_queue.empty():
            self.process_message()
        else:
            self.random_event()

    def process_message(self):
        sender_id, sender_clock = self.msg_queue.get()
        # RECEIVE rule for logical clock
        self.logical_clock = max(self.logical_clock, sender_clock) + 1
        self.log_event(event_type="RECEIVE", sender_id=sender_id)

    def random_event(self):
        r = random.randint(1, 10)
        if r == 1:
            self.send_message(to_peer=0)
        elif r == 2:
            self.send_message(to_peer=1)
        elif r == 3:
            # if we have 2 peers
            self.send_message(to_peer=0)
            self.send_message(to_peer=1)
        else:
            # INTERNAL event
            self.logical_clock += 1
            self.log_event(event_type="INTERNAL")

    def send_message(self, to_peer):
        if to_peer >= len(self.peers):
            return

        host, port = self.peers[to_peer]
        self.logical_clock += 1  # SEND rule

        message = logical_clock_pb2.ClockMessage(
            sender_id=self.vm_id,
            logical_clock=self.logical_clock
        )
        channel = grpc.insecure_channel(f"{host}:{port}")
        stub = logical_clock_pb2_grpc.VirtualMachineStub(channel)
        try:
            stub.SendMessage(message)
            self.log_event(event_type="SEND", receiver_id=to_peer)
        except Exception as e:
            self.log_event(event_type="SEND_ERROR", receiver_id=to_peer)

    def log_event(self, event_type, sender_id=None, receiver_id=None):
        event = {
            "system_time": datetime.datetime.now(),  # store as datetime obj
            "vm_id": self.vm_id,
            "event_type": event_type,
            "queue_len": self.msg_queue.qsize(),
            "logical_clock": self.logical_clock,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
        }
        self.local_log.append(event)

    def run_server(self):
        """
        gRPC server for receiving messages from peers.
        """
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        logical_clock_pb2_grpc.add_VirtualMachineServicer_to_server(self, server)
        server.add_insecure_port(f"[::]:{self.port}")
        server.start()
        print(f"VM {self.vm_id} server started on port {self.port}, clock_rate={self.clock_rate}")
        self._grpc_server = server
        server.wait_for_termination()

    def shutdown_server(self):
        """
        Stop the gRPC server.
        """
        if self._grpc_server is not None:
            self._grpc_server.stop(None)

    def SendMessage(self, request, context):
        """
        gRPC method: incoming message from peer.
        """
        sender_id = request.sender_id
        sender_clock = request.logical_clock
        self.msg_queue.put((sender_id, sender_clock))
        return logical_clock_pb2.Ack(status="Received")


def single_run(duration, run_index, output_dir):
    """
    Performs one simulation run for a given duration (in seconds).
    Creates 3 VMs, starts them, sleeps, stops them, combines their logs into a DataFrame,
    saves the DataFrame as CSV, logs info (like clock speeds) in run_info.txt,
    and calls analyze_logs to produce plots.
    """
    # Create the folder for this run (e.g., 'results/10seconds/run1')
    os.makedirs(output_dir, exist_ok=True)
    
    # Create three VMs
    vm0 = VirtualMachine(
        vm_id=0,
        peers=[("localhost", 50052), ("localhost", 50053)],
        port=50051
    )
    vm1 = VirtualMachine(
        vm_id=1,
        peers=[("localhost", 50051), ("localhost", 50053)],
        port=50052
    )
    vm2 = VirtualMachine(
        vm_id=2,
        peers=[("localhost", 50051), ("localhost", 50052)],
        port=50053
    )
    
    vms = [vm0, vm1, vm2]

    # Start them
    for vm in vms:
        vm.start()
    
    # Let them run for 'duration' seconds
    time.sleep(duration)
    
    # Stop them
    for vm in vms:
        vm.stop_flag = True
        vm.shutdown_server()
    
    # Join them
    for vm in vms:
        vm.join()
    
    # Combine logs
    all_events = []
    for vm in vms:
        all_events.extend(vm.local_log)
    
    df = pd.DataFrame(all_events)
    # Sort by system_time
    df.sort_values(by="system_time", inplace=True)
    
    # Save the combined DataFrame as CSV
    csv_path = os.path.join(output_dir, "all_vm_events.csv")
    df.to_csv(csv_path, index=False, date_format="%Y-%m-%dT%H:%M:%S.%f")
    print(f"Saved events to {csv_path}")

    # Write a small run_info.txt file with clock speeds and run info
    info_path = os.path.join(output_dir, "run_info.txt")
    with open(info_path, "w") as f:
        f.write(f"Run Index: {run_index}\n")
        f.write(f"Duration: {duration} seconds\n")
        f.write("Clock Rates:\n")
        for vm in vms:
            f.write(f"  VM {vm.vm_id} -> clock_rate={vm.clock_rate}\n")

    # Analyze logs & produce plots in the same folder
    analyze_logs(df, output_dir)


def main():
    """
    We'll do multiple runs for different durations:
    e.g. 5 runs at 10 seconds each, 5 runs at 60 seconds each.
    We'll store results in results/<duration>seconds/runX/.
    """
    durations = [10, 60]       # durations in seconds
    runs_per_duration = 5

    base_results_dir = "results"
    os.makedirs(base_results_dir, exist_ok=True)

    for dur in durations:
        # e.g. 'results/10seconds', 'results/60seconds'
        dur_folder = f"{dur}seconds"

        for run_i in range(1, runs_per_duration + 1):
            # e.g. 'results/10seconds/run1'
            run_dir = os.path.join(base_results_dir, dur_folder, f"run{run_i}")
            print(f"\n=== Starting run {run_i} for duration={dur} seconds ===")
            single_run(dur, run_i, run_dir)

    print("\nAll runs completed.")


if __name__ == "__main__":
    main()
