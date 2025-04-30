#!/bin/bash

# Stop all servers in the cluster

echo "Stopping all tetris servers..."

# Method 1: Try graceful shutdown first
for i in {0..2}; do
  PORT=$((3001 + $i))
  echo "Stopping server $i on port $PORT..."
  curl -X POST http://localhost:$PORT/kill 2>/dev/null || echo "Server $i not responding to HTTP"
done

# Method 2: Force kill if needed
for i in {0..2}; do
  PID_FILE="./server${i}.pid"
  if [ -f "$PID_FILE" ]; then
    PID=$(cat $PID_FILE)
    echo "Killing server $i with PID $PID"
    kill $PID 2>/dev/null || kill -9 $PID 2>/dev/null
    rm $PID_FILE
  fi
done

echo "All servers stopped"