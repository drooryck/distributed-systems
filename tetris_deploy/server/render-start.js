// Simple wrapper to ensure the server listens on the correct Render port

// Import the server script (which will use process.env.PORT)
require('./src/server.js');

// Log startup info
console.log(`Server starting on Render with PORT=${process.env.PORT}`);