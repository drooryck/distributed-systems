#!/bin/bash

# Start all three servers in the background
node src/server.js 0 &
PID0=$!
echo "Started Server 0 (Leader) with PID $PID0"

node src/server.js 1 &
PID1=$!
echo "Started Server 1 with PID $PID1"

node src/server.js 2 &
PID2=$!
echo "Started Server 2 with PID $PID2"

# Save PIDs to a file for later shutdown
echo "$PID0" > ./server0.pid
echo "$PID1" > ./server1.pid
echo "$PID2" > ./server2.pid

echo ""
echo "All servers started. Server addresses:"
echo "- Server 0: http://localhost:3001 (Leader)"
echo "- Server 1: http://localhost:3002"
echo "- Server 2: http://localhost:3003"
echo ""
echo "To kill a server for testing: ./kill-server.sh <server_id>"
echo "To kill all servers: ./stop-cluster.sh"

# Wait for all background processes
wait