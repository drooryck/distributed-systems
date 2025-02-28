import threading
import queue
import random
import time
import datetime

class VirtualMachine(threading.Thread):
    def __init__(self, vm_id, peers):
        """
        vm_id: An identifier for this virtual machine (e.g., 0, 1, 2)
        peers: A list of references to other virtual machines or, in future, 
               gRPC stubs to send messages over the network.
        """
        super().__init__()
        self.vm_id = vm_id
        # Random clock rate between 1 and 6 ticks per real second
        self.clock_rate = random.randint(1, 6)
        
        # Logical clock initialization
        self.logical_clock = 0
        
        # Our own incoming message queue (for demonstration)
        self.msg_queue = queue.Queue()
        
        # References to other machines (or stubs for gRPC)
        self.peers = peers
        
        # Open a dedicated log file for this VM
        self.log_file = open(f"vm_{vm_id}_log.txt", "w")
        
        # Flag to stop the thread
        self.stop_flag = False

    def run(self):
        """
        Main loop for this VM. The VM will 'tick' at self.clock_rate times per second.
        Each tick: check for incoming messages or do a random (send or internal) event.
        """
        while not self.stop_flag:
            start_time = time.time()
            
            # Perform up to clock_rate instructions within this 1-second window
            for _ in range(self.clock_rate):
                self.one_cycle()
                if self.stop_flag:
                    break
            
            # Sleep any remaining time in the 1-second window
            elapsed = time.time() - start_time
            to_sleep = 1.0 - elapsed
            if to_sleep > 0:
                time.sleep(to_sleep)

        # Close the log file
        self.log_file.close()

    def one_cycle(self):
        """
        One clock cycle: either process a queued message (if any) 
        or generate a random event (send or internal).
        """
        if not self.msg_queue.empty():
            self.process_incoming_message()
        else:
            self.random_event()

    def process_incoming_message(self):
        """
        Take one message off the queue, update logical clock accordingly,
        and log the receive event.
        """
        # Remove one message from the queue
        msg = self.msg_queue.get()
        sender_id, sender_clock = msg
        
        # Update logical clock on receive:
        # LC = max(LC, received_clock) + 1
        self.logical_clock = max(self.logical_clock, sender_clock) + 1

        # Log the receive
        # Logging the system time, queue length, logical clock, 
        # plus optional sender/receiver info for clarity
        system_time = datetime.datetime.now().isoformat()
        current_queue_len = self.msg_queue.qsize()
        log_line = (
            f"{system_time} | VM {self.vm_id} (RECEIVE) | "
            f"Sender={sender_id} | QueueLen={current_queue_len} | "
            f"LogicalClock={self.logical_clock}\n"
        )
        self.log_file.write(log_line)
        self.log_file.flush()

    def random_event(self):
        """
        If no message in queue, pick a random number 1..10.
          - 1: send to VM 0 (if it exists)
          - 2: send to VM 1 (if it exists)
          - 3: send to both 0 and 1 (if they exist)
          - otherwise: internal event
        """
        r = random.randint(1, 10)
        if r == 1:
            self.send_message(to_peer=0)
        elif r == 2:
            self.send_message(to_peer=1)
        elif r == 3:
            # Send to both if they exist
            self.send_message(to_peer=0)
            self.send_message(to_peer=1)
        else:
            # Internal event
            self.logical_clock += 1
            self.log_internal_event()

    def send_message(self, to_peer):
        """
        Send a message containing our local logical clock to one peer.
        Then update logical clock for the send event and log it.
        """
        # Defensive check (in case to_peer is out-of-range)
        if to_peer >= len(self.peers):
            return
        
        # Update logical clock on send
        self.logical_clock += 1
        
        # Put the message in the peer's queue (for demonstration).
        # Later, this could be replaced with a gRPC call: 
        #     self.peers[to_peer].SendMessage( self.vm_id, self.logical_clock )
        self.peers[to_peer].msg_queue.put((self.vm_id, self.logical_clock))
        # Log the send
        system_time = datetime.datetime.now().isoformat()
        current_queue_len = self.msg_queue.qsize()
        log_line = (
            f"{system_time} | VM {self.vm_id} (SEND) | "
            f"Receiver={self.peers[to_peer].vm_id} | QueueLen={current_queue_len} | "
            f"LogicalClock={self.logical_clock}\n"
        )
        self.log_file.write(log_line)
        self.log_file.flush()

    def log_internal_event(self):
        """
        Log an internal event (no send/receive, just a local clock tick).
        """
        system_time = datetime.datetime.now().isoformat()
        current_queue_len = self.msg_queue.qsize()
        log_line = (
            f"{system_time} | VM {self.vm_id} (INTERNAL) | "
            f"QueueLen={current_queue_len} | "
            f"LogicalClock={self.logical_clock}\n"
        )
        self.log_file.write(log_line)
        self.log_file.flush()


def main():
    # Create three VirtualMachine objects with dummy peers list initially
    vm_threads = []
    for i in range(3):
        vm = VirtualMachine(vm_id=i, peers=[])
        vm_threads.append(vm)
    
    # Now that the objects exist, assign them as peers to each other
    for i in range(3):
        # Peers are all other VMs except itself
        peers_list = [vm_threads[j] for j in range(3) if j != i]
        vm_threads[i].peers = peers_list
        print(list(vm_threads[i].peers))
    
    print('logic')
    # Start the VM threads
    for vm in vm_threads:
        vm.start()
        # print the vm id and clock rate
        print(f"VM {vm.vm_id} started with clock rate {vm.clock_rate}")
    # Let them run for at least 1 minute (5 seconds for now)
    time.sleep(10)
    
    # Signal them to stop
    for vm in vm_threads:
        vm.stop_flag = True
    
    # Join all threads
    for vm in vm_threads:
        vm.join()

    print("All VMs have stopped. Merging logs into global_log.txt...")

    combined_entries = []

    # For this example, we have three VMs, each with its own log file
    for i in range(3):
        filename = f"vm_{i}_log.txt"
        with open(filename, "r") as f:
            for line in f:
                # Each line starts with an ISO8601 datetime, e.g.:
                # 2025-02-27T12:34:56.789012 | VM 1 (SEND) | ...
                # We can split on " | " or parse more rigorously.
                
                # Let's split up to the first ' | '
                first_split = line.split(" | ", 1)
                if len(first_split) < 2:
                    # Not a well-formed log line; skip or handle error
                    continue
                datetime_str = first_split[0]  # e.g. 2025-02-27T12:34:56.789012
                
                try:
                    dt = datetime.datetime.fromisoformat(datetime_str)
                except ValueError:
                    # If it fails, skip or handle error
                    continue
                
                # Now store the parsed time and the entire original line
                combined_entries.append((dt, line))
    
    # Sort combined entries by the parsed datetime
    combined_entries.sort(key=lambda x: x[0])

    # Write them out to a global log file
    with open("global_log.txt", "w") as global_log:
        for dt, original_line in combined_entries:
            global_log.write(original_line)
    
    print("global_log.txt has been created and sorted by system time.")
    
    print("All VMs have stopped. Check vm_0_log.txt, vm_1_log.txt, vm_2_log.txt for logs.")

if __name__ == "__main__":
    main()