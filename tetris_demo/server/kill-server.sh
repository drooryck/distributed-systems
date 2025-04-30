#!/bin/bash

# Check if server_id is provided
if [ -z "$1" ]; then
  echo "Usage: ./kill-server.sh <server_id>"
  echo "Example: ./kill-server.sh 1"
  exit 1
fi

SERVER_ID=$1

# Two ways to kill a server:
# 1. Using the HTTP API endpoint (graceful shutdown)
# 2. Killing the process directly (simulate crash)

# Method 1: Try graceful shutdown first
PORT=$((3001 + $SERVER_ID))
echo "Attempting graceful shutdown of server $SERVER_ID on port $PORT..."
curl -X POST http://localhost:$PORT/kill

# Method 2: Force kill if needed
PID_FILE="./server${SERVER_ID}.pid"
if [ -f "$PID_FILE" ]; then
  PID=$(cat $PID_FILE)
  echo "Killing server $SERVER_ID with PID $PID"
  kill $PID 2>/dev/null || kill -9 $PID 2>/dev/null
  rm $PID_FILE
  echo "Server $SERVER_ID killed"
else
  echo "PID file not found for server $SERVER_ID"
fi