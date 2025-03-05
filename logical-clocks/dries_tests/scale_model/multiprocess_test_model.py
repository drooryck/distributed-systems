# File: scale_model.py
# same file as the scale_model in our main file, except it just spawns one process.

import os
import time
import random
import datetime
import multiprocessing

import pandas as pd
import grpc
from concurrent import futures

# If you still want proto definitions:
# from . import logical_clock_pb2
# from . import logical_clock_pb2_grpc

# Minimal VM code that runs in child process
class SingleVM:
    def __init__(self, vm_id, mode, clock_rate, log_file):
        """
        vm_id: int
        mode: str - 'internal', 'send_one', 'send_both', 'random'
        clock_rate: instructions per second
        log_file: path to CSV for logs
        """
        self.vm_id = vm_id
        self.mode = mode
        self.clock_rate = clock_rate
        self.log_file = log_file

        self.logical_clock = 0
        self.stop_flag = False
        self.local_log = []

    def run_loop(self, duration):
        """
        Runs for 'duration' seconds, generating events according to self.mode.
        """
        start_time = time.time()

        while (time.time() - start_time) < duration and not self.stop_flag:
            cycle_start = time.time()

            # Perform up to self.clock_rate instructions in 1 second
            for _ in range(self.clock_rate):
                if (time.time() - start_time) >= duration:
                    break
                if self.stop_flag:
                    break

                self.one_cycle()

            elapsed = time.time() - cycle_start
            to_sleep = 1.0 - elapsed
            if to_sleep > 0:
                time.sleep(to_sleep)

        self.write_logs()

    def one_cycle(self):
        """
        Generate an event based on mode:
          - 'internal': always internal event
          - 'send_one': always do a "send" event (to e.g. peer=0, but not tested)
          - 'send_both': log two "send" events
          - 'random': normal random calls
        """
        if self.mode == 'internal':
            self.internal_event()
        elif self.mode == 'send_one':
            self.send_event(to=0)
        elif self.mode == 'send_both':
            self.send_event(to=0)
            self.send_event(to=1)
        elif self.mode == 'random':
            # real random
            r = random.randint(1, 10)
            if r in [1,2,3]:
                self.send_event(to=r)  # just an example
            else:
                self.internal_event()
        else:
            # fallback => do nothing or internal
            self.internal_event()

    def internal_event(self):
        self.logical_clock += 1
        self.log_event("INTERNAL")

    def send_event(self, to=0):
        self.logical_clock += 1
        # "Sends" to some peer index 'to' (we're not actually testing the receiving side)
        self.log_event("SEND", receiver_id=to)

    def log_event(self, event_type, sender_id=None, receiver_id=None):
        event = {
            "system_time": datetime.datetime.now().isoformat(),
            "vm_id": self.vm_id,
            "event_type": event_type,
            "logical_clock": self.logical_clock,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
        }
        self.local_log.append(event)

    def write_logs(self):
        if not self.local_log:
            return
        df = pd.DataFrame(self.local_log)
        df.to_csv(self.log_file, index=False)

def run_vm_process(vm_id, mode, clock_rate, log_file, duration):
    """
    Entry point for the child process. We create SingleVM and run it.
    """
    vm = SingleVM(vm_id, mode, clock_rate, log_file)
    vm.run_loop(duration)

def single_run(mode, duration=3):
    """
    Orchestrates a single child process for 'duration' seconds in the given 'mode'.
    Returns a DataFrame with that VM's logs.
    """
    log_file = f"vm_{mode}_log.csv"
    clock_rate = random.randint(1, 6)  # or pass it in

    # Start child process
    p = multiprocessing.Process(
        target=run_vm_process,
        args=(0, mode, clock_rate, log_file, duration)
    )
    p.start()

    # Wait
    p.join()

    # Load logs
    if os.path.exists(log_file):
        df = pd.read_csv(log_file)
        return df
    else:
        return pd.DataFrame()
