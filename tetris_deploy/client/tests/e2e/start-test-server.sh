#!/bin/bash
# This script starts a test server on a fixed port for e2e tests

cd ../../server
NODE_ENV=test PORT=4500 node src/server.js