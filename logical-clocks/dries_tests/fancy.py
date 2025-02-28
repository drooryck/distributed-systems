import threading
import queue
import random
import time
import datetime
import os

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

class VirtualMachine(threading.Thread):
    def __init__(self, vm_id, peers):
        super().__init__()
        self.vm_id = vm_id  # Global VM ID
        self.clock_rate = random.randint(1, 6)  # Ticks per second
        self.logical_clock = 0
        
        self.msg_queue = queue.Queue()
        self.peers = peers  # List of peer references (other VMs)
        
        # Local in-memory log storage
        self.local_log = []
        
        self.stop_flag = False

    def run(self):
        while not self.stop_flag:
            start_time = time.time()
            
            # Perform up to self.clock_rate instructions per second
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
            self.process_incoming_message()
        else:
            self.random_event()

    def process_incoming_message(self):
        sender_id, sender_clock = self.msg_queue.get()
        # Update logical clock based on message received
        self.logical_clock = max(self.logical_clock, sender_clock) + 1
        
        # Log the receive event with correct global VM IDs
        self.log_event(
            event_type="RECEIVE",
            sender_id=sender_id,  # Global sender ID
            receiver_id=self.vm_id  # Global receiver ID
        )

    def random_event(self):
        r = random.randint(1, 10)
        if r == 1:
            self.send_message(self.peers[0].vm_id)
        elif r == 2 and len(self.peers) > 1:
            self.send_message(self.peers[1].vm_id)
        elif r == 3 and len(self.peers) > 1:
            self.send_message(self.peers[0].vm_id)
            self.send_message(self.peers[1].vm_id)
        else:
            self.logical_clock += 1
            self.log_event(event_type="INTERNAL")

    def send_message(self, receiver_vm_id):
        # Update logical clock on send
        self.logical_clock += 1
        
        # Find the actual peer object that matches the receiver_vm_id
        for peer in self.peers:
            if peer.vm_id == receiver_vm_id:
                peer.msg_queue.put((self.vm_id, self.logical_clock))
                break

        # Log the send event with correct global IDs
        self.log_event(event_type="SEND", sender_id=self.vm_id, receiver_id=receiver_vm_id)

    def log_event(self, event_type, sender_id=None, receiver_id=None):
        """
        Stores log events in memory with global VM IDs.
        """
        event = {
            "system_time": datetime.datetime.now().isoformat(),
            "vm_id": self.vm_id,
            "event_type": event_type,
            "queue_len": self.msg_queue.qsize(),
            "logical_clock": self.logical_clock,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
        }
        self.local_log.append(event)

def analyze_logs(df):
    """
    Analyze and plot event data from the simulation.
    """

    # Convert system_time to datetime for proper sorting
    df["system_time"] = pd.to_datetime(df["system_time"])
    df.sort_values(by="system_time", inplace=True)

    # Create a folder for storing plots
    plot_dir = "plots"
    os.makedirs(plot_dir, exist_ok=True)

    # --- 1) Plot Logical Clock Over Time ---
    plt.figure(figsize=(10,6))
    sns.lineplot(data=df, x="system_time", y="logical_clock", hue="vm_id", marker="o")
    plt.title("Logical Clock over Time (by VM)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "logical_clock_over_time.png"))
    plt.close()

    # --- 2) Plot Queue Length Over Time ---
    plt.figure(figsize=(10,6))
    sns.lineplot(data=df, x="system_time", y="queue_len", hue="vm_id", marker="o")
    plt.title("Queue Length over Time (by VM)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "queue_length_over_time.png"))
    plt.close()

    # --- 3) Count of Event Types per VM ---
    event_counts = df.groupby(["vm_id", "event_type"]).size().reset_index(name="count")
    print("\nEvent counts by VM and Event Type:")
    print(event_counts)

    plt.figure(figsize=(8,5))
    sns.countplot(data=df, x="event_type", hue="vm_id")
    plt.title("Distribution of Event Types by VM")
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "event_type_distribution.png"))
    plt.close()

    print(f"\nPlots saved to '{plot_dir}/'.")

def main():
    # Create VMs with empty peer lists initially
    vm_threads = []
    for i in range(3):
        vm = VirtualMachine(vm_id=i, peers=[])
        vm_threads.append(vm)
    
    # Assign correct peer references
    for i in range(3):
        peers_list = [vm_threads[j] for j in range(3) if j != i]
        vm_threads[i].peers = peers_list
    
    # Start the VMs
    for vm in vm_threads:
        vm.start()
    
    # Let the VMs run for 10 seconds
    time.sleep(10)
    
    # Stop all VMs
    for vm in vm_threads:
        vm.stop_flag = True
    
    # Wait for threads to finish
    for vm in vm_threads:
        # print rate
        print(f"VM {vm.vm_id} stopped with clock rate {vm.clock_rate}")
        vm.join()
    
    # Merge logs into a DataFrame
    all_events = []
    for vm in vm_threads:
        all_events.extend(vm.local_log)
    
    df = pd.DataFrame(all_events)
    
    # Run analysis
    analyze_logs(df)

if __name__ == "__main__":
    main()
