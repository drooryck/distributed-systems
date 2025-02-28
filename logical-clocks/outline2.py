import threading
import queue
import random
import time
import datetime
import asyncio

# For gRPC since it uses ThreadPoolExecutor
from concurrent import futures

import grpc
import logical_clock_pb2
import logical_clock_pb2_grpc


class VirtualMachine(threading.Thread):
    def __init__(self, vm_id, peers, port):
        """
        vm_id : An identifier for this virtual machine (e.g. 0, 1, or 2)
        peers : A list of references to other VirtualMachine objects
        port : The port number to bind the gRPC server to
        """
        super().__init__()
        self.vm_id = vm_id
        
        # Random clock rate between 1 and 6 ticks per second
        self.clock_rate = random.randint(1, 6)
        
        # Logical clock initialization
        self.logical_clock = 0
        
        # Our own incoming message queue
        self.msg_queue = queue.Queue()
        
        # References to other machines (list of (host, port) tuples).
        self.peers = peers
        
        # Open a log file for this VM
        self.log_file = open(f"vm_{vm_id}_log.txt", "w")

        self.port = port
        
        # Control flag if we want to stop
        self.stop_flag = False

    def run(self):
        """
        Main loop for this VM. The VM will run at self.clock_rate ticks per second.
        Each tick means "perform one instruction" (check queue or do a random event).
        Ticks are grouped into 1-second blocks.
        """
        # Start the gRPC server in a separate daemon thread.
        server_thread = threading.Thread(target=self.run_server, daemon=True)
        server_thread.start()
        
        while not self.stop_flag:
            start_time = time.time()
            
            # Perform up to self.clock_rate instructions in this second.
            for _ in range(self.clock_rate):
                self.one_cycle()
                if self.stop_flag:
                    break
            
            # Sleep the remainder of the second, if any.
            elapsed = time.time() - start_time
            sleep_time = 1.0 - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # Close the log file before exiting.
        self.log_file.close()

    def one_cycle(self):
        """
        One clock cycle ("instruction"):
         1) If there's a message in the queue, process it.
         2) Otherwise, perform a random event (send or internal).
        """
        if not self.msg_queue.empty():
            self.process_message()
        else:
            self.random_event()

    def process_message(self):
        """
        Process exactly one message from the queue.
        Update the logical clock and log the event.
        """
        msg = self.msg_queue.get()
        sender_id, sender_clock = msg
        
        old_clock = self.logical_clock
        self.logical_clock = max(self.logical_clock, sender_clock) + 1
        
        self.log_event(
            event_type="RECEIVE",
            detail=f"From VM {sender_id}, old_clock={old_clock}, msg_clock={sender_clock}"
        )

    def random_event(self):
        """
        If no message is in the queue, pick a random number in 1..10 and:
          - If 1: send to peer 0.
          - If 2: send to peer 1.
          - If 3: send to both peers.
          - Otherwise: perform an internal event.
        """
        r = random.randint(1, 10)
        if r == 1:
            self.send_message(to_peer=0)
        elif r == 2:
            self.send_message(to_peer=1)
        elif r == 3:
            self.send_message(to_peer=0)
            self.send_message(to_peer=1)
        else:
            old_clock = self.logical_clock
            self.logical_clock += 1
            self.log_event(
                event_type="INTERNAL",
                detail=f"old_clock={old_clock} -> new_clock={self.logical_clock}"
            )

    def send_message(self, to_peer):
        """
        Send a message containing our local logical clock to a specific peer using gRPC.
        Update the logical clock (send event) and log the event.
        """
        if to_peer >= len(self.peers):
            return
        
        # Retrieve the peer's host and port.
        peer_host, peer_port = self.peers[to_peer]
        old_clock = self.logical_clock
        self.logical_clock += 1
        
        # Prepare the message using protobuf.
        message = logical_clock_pb2.ClockMessage(
            sender_id=self.vm_id,
            logical_clock=self.logical_clock
        )
        
        # Create a gRPC channel and stub, then send the message.
        channel = grpc.insecure_channel(f"{peer_host}:{peer_port}")
        stub = logical_clock_pb2_grpc.VirtualMachineStub(channel)
        try:
            response = stub.SendMessage(message)
            self.log_event(
                event_type="SEND",
                detail=f"To VM at {peer_host}:{peer_port}, old_clock={old_clock} -> new_clock={self.logical_clock}, response: {response.status}"
            )
        except Exception as e:
            self.log_event(
                event_type="SEND_ERROR",
                detail=f"Error sending to {peer_host}:{peer_port}: {e}"
            )

    def log_event(self, event_type, detail=""):
        """
        Write a log entry: system time, local logical clock, event type, queue length, and extra detail.
        """
        system_time = datetime.datetime.now().isoformat()
        queue_len = self.msg_queue.qsize()
        log_line = (f"{system_time} | VM {self.vm_id} | LogicalClock={self.logical_clock} | "
                    f"QueueLen={queue_len} | {event_type} | {detail}\n")
        self.log_file.write(log_line)
        self.log_file.flush()

    def run_server(self):
        """
        Starts the gRPC server to listen on the specified port for incoming messages.
        """
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        logical_clock_pb2_grpc.add_VirtualMachineServicer_to_server(self, server)
        server.add_insecure_port(f"[::]:{self.port}")
        server.start()
        print(f"VM {self.vm_id} gRPC server started on port {self.port} with clock rate {self.clock_rate}")
        server.wait_for_termination()

    # gRPC service implementation.
    def SendMessage(self, request, context):
        """
        When a gRPC SendMessage call is received, place the message in the local message queue.
        """
        sender_id = request.sender_id
        sender_clock = request.logical_clock
        self.msg_queue.put((sender_id, sender_clock))
        return logical_clock_pb2.Ack(status="Received")

def main():
    """
    Create three virtual machines that use gRPC for message passing.
    Each VM is assigned a unique port, and peers are specified as (host, port) tuples.
    """
    # Instantiate VMs with ports and peer addresses.
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
    
    # Start all VM threads.
    vm0.start()
    vm1.start()
    vm2.start()
    
    # Let them run for at least one minute.
    time.sleep(60)
    
    # Signal the VMs to stop.
    vm0.stop_flag = True
    vm1.stop_flag = True
    vm2.stop_flag = True
    
    # Join the threads.
    vm0.join()
    vm1.join()
    vm2.join()
    
    print("All VMs have stopped. Logs should be in vm_0_log.txt, vm_1_log.txt, vm_2_log.txt.")

if __name__ == "__main__":
    main()