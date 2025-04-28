#!/bin/bash

# Start all three nodes of the Tetris server cluster
echo "Starting Tetris server cluster with 3 nodes..."

# Start Node 1
echo "Starting Node 1 on port 3001..."
NODE_ID=node1 node src/clusterServer.js &
NODE1_PID=$!
echo "Node 1 started with PID: $NODE1_PID"

# Wait a moment to ensure the first node is up
sleep 2

# Start Node 2
echo "Starting Node 2 on port 3002..."
NODE_ID=node2 node src/clusterServer.js &
NODE2_PID=$!
echo "Node 2 started with PID: $NODE2_PID"

# Wait a moment
sleep 2

# Start Node 3
echo "Starting Node 3 on port 3003..."
NODE_ID=node3 node src/clusterServer.js &
NODE3_PID=$!
echo "Node 3 started with PID: $NODE3_PID"

echo "All nodes started. Press Ctrl+C to stop all nodes."

# Save PIDs for cleanup
echo "$NODE1_PID $NODE2_PID $NODE3_PID" > .cluster_pids

# Handle Ctrl+C gracefully
function cleanup() {
    echo "Stopping all nodes..."
    if [ -f .cluster_pids ]; then
        for pid in $(cat .cluster_pids); do
            kill $pid 2>/dev/null
        done
        rm .cluster_pids
    fi
    exit 0
}

trap cleanup INT

# Wait for all processes
wait