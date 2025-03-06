import os
import threading
import queue
import random
import time
import datetime
import multiprocessing

# gRPC imports
import grpc
from concurrent import futures

# Data analysis and plotting
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Proto-generated imports
import logical_clock_pb2
import logical_clock_pb2_grpc

from google.protobuf.empty_pb2 import Empty

def analyze_logs(df, output_dir):
    """
    Analyze and plot event data from the simulation, saving plots in output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Convert system_time to datetime and sort
    df["system_time"] = pd.to_datetime(df["system_time"])
    df.sort_values(by="system_time", inplace=True)

    # Use the default Seaborn color palette
    sns.set_palette("muted")

    # Line plots for Logical Clock & Queue Length
    for metric, title, filename in [
        ("logical_clock", "Logical Clock over Time (by VM)", "logical_clock_over_time.png"),
        ("queue_len", "Queue Length over Time (by VM)", "queue_length_over_time.png")
    ]:
        plt.figure(figsize=(10,6))
        sns.lineplot(data=df, x="system_time", y=metric, hue="vm_id", marker="o")
        plt.title(title)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, filename))
        plt.close()

    # Event type counts
    event_counts = df.groupby(["vm_id", "event_type"]).size().unstack(fill_value=0)

    # Stacked Bar Charts
    for index, xlabel, filename in [
        ("event_type", "Event Type", "event_type_distribution.png"),
        ("vm_id", "VM ID", "event_type_distribution_by_vm.png")
    ]:
        event_counts.plot(kind="bar", stacked=True, figsize=(8,5))
        plt.title(f"Distribution of Event Types (Stacked by {xlabel})")
        plt.xlabel(xlabel)
        plt.ylabel("Count")
        plt.xticks(rotation=45 if index == "event_type" else 0)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, filename))
        plt.close()

    # Compute and plot drift over time
    df["time_bin"] = df["system_time"].dt.floor("S")
    drift_df = df.groupby("time_bin")["logical_clock"].agg(["max", "min"]).reset_index()
    drift_df["drift"] = drift_df["max"] - drift_df["min"]

    plt.figure(figsize=(10,6))
    sns.lineplot(data=drift_df, x="time_bin", y="drift", marker="o")
    plt.title("Relative Drift Over Time\n(Difference between max and min logical clocks)")
    plt.xlabel("System Time")
    plt.ylabel("Drift (max - min)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "relative_drift_over_time.png"))
    plt.close()

    print(f"Plots saved to '{output_dir}/'.\n")


class VirtualMachine(logical_clock_pb2_grpc.VirtualMachineServicer):
    """
    Each VirtualMachine runs in its own process, but uses threads internally:
    - One thread to run the gRPC server (listening for incoming messages).
    - One thread to execute the main loop at the designated clock_rate.
    """
    def __init__(self, vm_id, peers, port, clock_rate, log_file):
        self.vm_id = vm_id
        self.clock_rate = clock_rate
        self.logical_clock = 0
        
        self.msg_queue = queue.Queue()  # for incoming messages
        self.peers = peers              # (host, port) of other machines
        
        self.local_log = []  # store log events as dictionaries
        self.port = port
        self.stop_flag = False
        self._grpc_server = None
        self.log_file = log_file  # where this VM writes its CSV events

        # Create a lock for the logical clock
        self.clock_lock = threading.Lock()

    def main_loop(self):
        """
        Executes self.clock_rate instructions per second until stop_flag is set,
        spaced out so each cycle occurs every 1/self.clock_rate seconds.
        """
        while not self.stop_flag:
            for _ in range(self.clock_rate):
                if self.stop_flag:
                    break
                cycle_start = time.time()

                self.one_cycle()

                # We'll sleep whatever remains of (1.0 / clock_rate)
                fraction = 1.0 / self.clock_rate
                elapsed = time.time() - cycle_start
                to_sleep = fraction - elapsed
                if to_sleep > 0:
                    time.sleep(to_sleep)

        # Final step: write out the logs
        self.write_logs_to_file()

    def one_cycle(self):
        """
        One cycle checks if there is an incoming message; if so, processes it.
        Otherwise, performs a random event (SEND or INTERNAL).
        """
        if not self.msg_queue.empty():
            self.process_message()
        else:
            self.random_event()

    def process_message(self):
        """
        Dequeues one (sender_id, sender_clock) from msg_queue.
        RECEIVE rule for logical clock: L = max(L, sender_clock) + 1
        """
        sender_id, sender_clock = self.msg_queue.get()
        with self.clock_lock:
            self.logical_clock = max(self.logical_clock, sender_clock) + 1
        self.log_event(event_type="RECEIVE", sender_id=sender_id)

    def random_event(self):
        """
        With probability:
         - 3/10 => SEND to a subset of peers (one, several, or all).
         - 7/10 => INTERNAL event.
        """
        r = random.randint(1, 10)
        if r == 1:
            self.send_message(to_peer=0)
        elif r == 2:
            self.send_message(to_peer=1)
        elif r == 3:
            # if there are more than 2 peers, send to the first two peers as an example
            self.send_message(to_peer=0)
            self.send_message(to_peer=1)
        else:
            # INTERNAL event
            with self.clock_lock:
                self.logical_clock += 1
            self.log_event(event_type="INTERNAL")

    def send_message(self, to_peer):
        if to_peer >= len(self.peers):
            return

        host, port = self.peers[to_peer]
        with self.clock_lock:
            self.logical_clock += 1
            current_clock = self.logical_clock

        message = logical_clock_pb2.ClockMessage(
            sender_id=self.vm_id,
            logical_clock=current_clock
        )

        channel = grpc.insecure_channel(f"{host}:{port}")
        stub = logical_clock_pb2_grpc.VirtualMachineStub(channel)
        try:
            stub.SendMessage(message)
            self.log_event(event_type="SEND", receiver_id=to_peer)
        except Exception:
            self.log_event(event_type="SEND_ERROR", receiver_id=to_peer)

    def log_event(self, event_type, sender_id=None, receiver_id=None):
        event = {
            "system_time": datetime.datetime.now(),
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
        gRPC server for receiving messages (in its own thread).
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

    def StopVM(self, request, context):
        """
        RPC call that signals this VM to stop.
        """
        self.stop_flag = True
        return logical_clock_pb2.Ack(status="Stopping")

    def write_logs_to_file(self):
        """
        Write the local logs to the assigned CSV file.
        """
        if not self.local_log:
            return
        df = pd.DataFrame(self.local_log)
        df.sort_values(by="system_time", inplace=True)
        df.to_csv(self.log_file, index=False, date_format="%Y-%m-%dT%H:%M:%S.%f")


def run_vm_process(vm_id, peers, port, clock_rate, log_file):
    """
    The entry point for each VM process. Sets up the VirtualMachine instance,
    starts the gRPC server thread, starts the main loop thread, and waits for them.
    """
    vm = VirtualMachine(vm_id, peers, port, clock_rate, log_file)

    # Thread for gRPC server
    server_thread = threading.Thread(target=vm.run_server, daemon=True)
    server_thread.start()

    # Thread for main loop
    main_loop_thread = threading.Thread(target=vm.main_loop, daemon=True)
    main_loop_thread.start()

    # Wait for main loop to exit (StopVM sets stop_flag)
    main_loop_thread.join()

    # Shut down server
    vm.shutdown_server()
    server_thread.join()


def single_run(duration, run_index, output_dir):
    """
    Performs one simulation run for a given duration (in seconds).
    Spawns 5 VM processes, sleeps, stops them via RPC, merges their logs,
    then calls analyze_logs to produce plots.
    """
    # Create the folder for this run (e.g., 'results/10seconds/run1')
    os.makedirs(output_dir, exist_ok=True)

    num_vms = 5

    # Random clock rates for the VMs
    clock_rates = [random.randint(1, 6) for _ in range(num_vms)]
    
    # Hard-code ports for each VM, e.g., 50051, 50052, 50053, 50054, 50055
    ports = [50051 + i for i in range(num_vms)]
    
    # Peers: for each VM, create a list of all other VMs
    peer_lists = []
    for i in range(num_vms):
        peers = [("localhost", ports[j]) for j in range(num_vms) if j != i]
        peer_lists.append(peers)

    # CSV log files for each VM
    log_files = [os.path.join(output_dir, f"vm{i}_events.csv") for i in range(num_vms)]
    
    # Create and start processes
    processes = []
    for i in range(num_vms):
        p = multiprocessing.Process(
            target=run_vm_process,
            args=(i, peer_lists[i], ports[i], clock_rates[i], log_files[i])
        )
        p.start()
        processes.append(p)
    
    # Let them run for 'duration' seconds
    time.sleep(duration)
    
    # Stop them via RPC calls
    for i in range(num_vms):
        channel = grpc.insecure_channel(f"localhost:{ports[i]}")
        stub = logical_clock_pb2_grpc.VirtualMachineStub(channel)
        try:
            stub.StopVM(Empty())
        except Exception as e:
            print(f"Error stopping VM {i}: {e}")
    
    # Join them
    for p in processes:
        p.join()
    
    # Combine logs
    all_events = []
    for i in range(num_vms):
        if os.path.exists(log_files[i]):
            df_vm = pd.read_csv(log_files[i])
            all_events.extend(df_vm.to_dict("records"))

    df = pd.DataFrame(all_events)
    if not df.empty:
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
            for vm_id, cr in enumerate(clock_rates):
                f.write(f"  VM {vm_id} -> clock_rate={cr}\n")

        # Analyze logs & produce plots in the same folder
        analyze_logs(df, output_dir)
    else:
        print("No events were logged. Check for issues in VM processes.")


def main():
    """
    We'll do multiple runs for different durations:
    e.g. 5 runs at 10 seconds each, 5 runs at 60 seconds each.
    We'll store results in results/<duration>seconds/runX/.
    """
    durations = [60]       # durations in seconds
    runs_per_duration = 5

    base_results_dir = "results"
    os.makedirs(base_results_dir, exist_ok=True)

    for dur in durations:
        # e.g. 'results/10seconds', 'results/60seconds'
        dur_folder = "five_machines"

        for run_i in range(1, runs_per_duration + 1):
            # e.g. 'results/10seconds/run1'
            run_dir = os.path.join(base_results_dir, dur_folder, f"run{run_i}")
            print(f"\n=== Starting run {run_i} for duration={dur} seconds ===")
            single_run(dur, run_i, run_dir)

    print("\nAll runs completed.")


if __name__ == "__main__":
    main()