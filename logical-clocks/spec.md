# Logical Clocks Project Specification

## Project Directory Structure

```logical-clocks/
│── dries_tests/                        
│   │── results/
│   │   │── 10seconds/
│   │   │   │── run1/
│   │   │   │   ├── vm0_events.csv
│   │   │   │   ├── vm1_events.csv
│   │   │   │   ├── vm2_events.csv
│   │   │   │   ├── all_vm_events.csv
│   │   │   │   ├── event_type_distribution_by_vm.png
│   │   │   │   ├── event_type_distribution.png
│   │   │   │   ├── queue_length_over_time.png
│   │   │   │   ├── relative_drift_over_time.png
│   │   │   │   └── run_info.txt
│   │   │   │── run2/
│   │   │   │── run3/
│   │   │   │── run4/
│   │   │   │── run5/
│   │   │── 60seconds/
│   │   │   ├── run1/
│   │   │   ├── run2/
│   │   │   ├── run3/
│   │   │   ├── run4/
│   │   │   └── run5/
│   │   ├── smaller_clock_cycles_results/
│   │   │   ├── run1/
│   │   │   ├── run2/
│   │   │   ├── run3/
│   │   │   ├── run4/
│   │   │   └── run5/
│   │   └── smaller_internal_prob/
│   │       ├── run1/
│   │       ├── run2/
│   │       ├── run3/
│   │       ├── run4/
│   │       └── run5/
|   |-- scale_model
|   |-- tests
│   └── spec.md
|   
└── ...


Each subfolder under `results/` corresponds to a distinct experimental setting and duration:

- **10seconds/**: Contains short, 10-second sample runs.
- **60seconds/**: Contains default settings with 60-second runs.
- **smaller_clock_cycles_results/**: Restricts the clock‐rate range to 1–3.
- **smaller_internal_prob/**: Reduces the probability of an internal event from 70% to 25%.

Within each subfolder, there are further subfolders named `run1`, `run2`, etc., each containing:
- ``vm0_events.csv``, ``vm1_events.csv``, ``vm2_events.csv``: Logs of each machine’s events.
- ``all_vm_events.csv``: A merged log of all three machines, sorted by system time (a “god’s eye” view).
- ``run_info.txt``: Contains assigned clock rates and basic run metadata.
- Visualizations:
  - ``event_type_distribution.png`` and ``event_type_distribution_by_vm.png``
  - ``logical_clock_over_time.png``
  - ``queue_length_over_time.png``
  - ``relative_drift_over_time.png``

We include a **10seconds** folder for short runs to confirm correctness before the spec’s required **60-second** experiments.

## Explanation of Experimental Folders

1. **10seconds**  
   Short demonstration runs to confirm correctness.

2. **60seconds**  
   The primary runs meeting the assignment’s requirement of at least one minute.

3. **smaller_clock_cycles_results**  
   Runs where the VM clock‐rate range is narrowed (e.g. 1–3 instead of 1–6).

4. **smaller_internal_prob**  
   Runs where the probability of an internal event is decreased (e.g. 25% instead of 70%), boosting SEND/RECEIVE frequency.

Each folder includes **5 runs** to gather multiple data points.

## Code Documentation

1. **``fancy.py``**  
   - Implements a **Lamport Logical Clock**–based simulation in Python.
   - Uses **gRPC** for inter-process communication.
   - Spawns three virtual machines, each in a separate process.
   - Each VM listens on a unique port, processes messages via a network queue, and logs events.
   - After the run, logs are merged and analyzed with **pandas** and **matplotlib**.

2. **Flow**  
   - ``main()`` orchestrates multiple runs for different durations.
   - ``single_run(...)`` sets up the environment, starts VMs, waits the specified duration, stops them, collects logs, and calls ``analyze_logs``.
   - ``VirtualMachine`` (or ``VirtualMachineProcess``) handles each VM’s logic:
     - Maintains a message queue (``msg_queue``) for inbound messages.
     - Uses random events (``INTERNAL``, ``SEND``, ``RECEIVE``) to simulate asynchronous distributed behavior.
     - Writes events to CSV logs, including system time, logical clock, event type, and queue length.

3. **Key Features**  
   - **Random Clock Rate**: Each VM’s clock rate is randomly assigned between 1–6 ticks/second (or 1–3 in the smaller-cycle runs).
   - **Random Event Generation**: Probability of sending vs. internal events can be adjusted for different variational experiments (70% internal, 30% send, or 25% internal, 75% send).
   - **Logical Clock**: On ``INTERNAL`` or ``SEND``, increments by 1; on ``RECEIVE``, sets ``L = max(L, sender_clock) + 1``.
   - **Queue**: Received messages are queued and processed at the VM’s clock rate.
   - **Analysis**: The final CSV is read into **pandas** to generate plots (logical clock over time, queue length, event distribution, drift, etc.).

4. Other stuff
We added a nice test suite for making sure that the messages we sent are actually logged correctly for a single process.

This setup meets the assignment’s requirement of modeling multiple asynchronous VMs on one machine, each as a separate process that communicates via sockets (gRPC). The logs and plots in each ``results/`` subfolder illustrate how clock drift, event distribution, and queue behavior evolve under various experimental conditions.