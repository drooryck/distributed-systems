const path = require('path');
const ClusterServer = require('./cluster/ClusterServer');
const gameStateFunctions = require('./gameState');

// Get the node ID from the command line arguments or environment variable
const nodeId = process.env.NODE_ID || 'node1';
const configPath = path.join(__dirname, '../clusterConfig.json');

console.log(`Starting Tetris cluster server node: ${nodeId}`);

// Create and initialize the cluster server
const server = new ClusterServer(nodeId, configPath);

// Initialize with game state functions
server.initialize(gameStateFunctions);

// Start the server
server.start();

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log(`Shutting down node ${nodeId}...`);
  server.shutdown();
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log(`Shutting down node ${nodeId}...`);
  server.shutdown();
  process.exit(0);
});