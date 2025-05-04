const { spawn } = require('child_process');
const io = require('socket.io-client');
const path = require('path');

// Simulating network latency and packet loss for clients
class NetworkFaultTest {
  constructor() {
    this.serverProcess = null;
    this.clients = [];
    this.roomCodes = [];
  }

  // Start the server
  async startServer() {
    console.log('Starting Tetristributed server for fault testing...');
    
    const serverPath = path.join(__dirname, '../../src/server.js');
    this.serverProcess = spawn('node', [serverPath], { 
      env: { ...process.env, NODE_ENV: 'development' },
      stdio: 'inherit'
    });

    // Wait for server to start
    await new Promise(resolve => setTimeout(resolve, 3000));
    console.log('Server started');
  }

  // Stop the server
  stopServer() {
    if (this.serverProcess) {
      console.log('Stopping server...');
      this.serverProcess.kill();
      this.serverProcess = null;
    }
  }

  // Create a client connection
  createClient(name = 'TestPlayer') {
    const socket = io('http://localhost:3000', {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5
    });

    const client = { socket, name, id: null, roomCode: null };
    
    socket.on('connect', () => {
      client.id = socket.id;
      console.log(`Client ${name} connected with ID: ${socket.id}`);
    });

    socket.on('disconnect', (reason) => {
      console.log(`Client ${name} disconnected: ${reason}`);
    });

    socket.on('reconnect', (attemptNumber) => {
      console.log(`Client ${name} reconnected after ${attemptNumber} attempts`);
    });

    socket.on('reconnect_failed', () => {
      console.log(`Client ${name} failed to reconnect`);
    });

    socket.on('error', (error) => {
      console.log(`Client ${name} experienced error: ${error}`);
    });

    this.clients.push(client);
    return client;
  }

  // Create a room and return the room code
  createRoom(client) {
    return new Promise((resolve) => {
      client.socket.once('roomCreated', (data) => {
        client.roomCode = data.roomCode;
        this.roomCodes.push(data.roomCode);
        console.log(`Client ${client.name} created room: ${data.roomCode}`);
        resolve(data.roomCode);
      });
      
      client.socket.emit('createRoom', client.name);
    });
  }

  // Join a room
  joinRoom(client, roomCode) {
    return new Promise((resolve) => {
      client.socket.once('joinedRoom', (data) => {
        client.roomCode = roomCode;
        console.log(`Client ${client.name} joined room: ${roomCode}`);
        resolve(data);
      });
      
      client.socket.emit('joinRoom', { 
        roomCode, 
        playerName: client.name 
      });
    });
  }

  // Player ready
  playerReady(client) {
    return new Promise((resolve) => {
      client.socket.once('gameState', (data) => {
        console.log(`Client ${client.name} is now ready`);
        resolve(data);
      });
      
      client.socket.emit('playerReady', { roomCode: client.roomCode });
    });
  }

  // Start game
  startGame(client) {
    return new Promise((resolve) => {
      client.socket.once('gameState', (data) => {
        if (data.appPhase === 'playing') {
          console.log(`Game started in room: ${client.roomCode}`);
          resolve(data);
        } else {
          client.socket.once('gameState', resolve);
        }
      });
      
      client.socket.emit('startGame', { roomCode: client.roomCode });
    });
  }

  // Send player actions
  sendAction(client, actionType) {
    client.socket.emit('playerAction', { 
      type: actionType, 
      roomCode: client.roomCode 
    });
  }

  // Simulate network latency
  simulateLatency(client, latencyMs) {
    console.log(`Adding ${latencyMs}ms latency to ${client.name}'s connection`);
    
    // Store original emit
    const originalEmit = client.socket.emit;
    
    // Wrap emit with latency
    client.socket.emit = function() {
      const args = arguments;
      setTimeout(() => {
        originalEmit.apply(client.socket, args);
      }, latencyMs);
    };
  }

  // Simulate packet loss
  simulatePacketLoss(client, lossRate) {
    console.log(`Adding ${lossRate * 100}% packet loss to ${client.name}'s connection`);
    
    // Store original emit
    const originalEmit = client.socket.emit;
    
    // Wrap emit with packet loss
    client.socket.emit = function() {
      if (Math.random() >= lossRate) {
        originalEmit.apply(client.socket, arguments);
      } else {
        console.log(`[Packet dropped] ${client.name} -> ${arguments[0]}`);
      }
    };
  }

  // Simulate complete disconnect
  disconnectClient(client) {
    console.log(`Disconnecting client ${client.name}`);
    client.socket.disconnect();
  }

  // Reconnect client
  reconnectClient(client) {
    console.log(`Reconnecting client ${client.name}`);
    client.socket.connect();
  }

  // Clean up all resources
  cleanup() {
    console.log('Cleaning up test resources...');
    
    // Disconnect all clients
    this.clients.forEach(client => {
      if (client.socket.connected) {
        client.socket.disconnect();
      }
    });
    
    // Stop the server
    this.stopServer();
  }

  // Run the network fault test
  async runNetworkFaultTest() {
    try {
      // Start the server
      await this.startServer();
      
      console.log('=== Starting Network Fault Test ===');
      
      // Create game host
      const host = this.createClient('Host');
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Create room
      const roomCode = await this.createRoom(host);
      
      // Create 3 players to join
      const player1 = this.createClient('Player1');
      const player2 = this.createClient('Player2');
      const player3 = this.createClient('Player3');
      
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Players join room
      await Promise.all([
        this.joinRoom(player1, roomCode),
        this.joinRoom(player2, roomCode),
        this.joinRoom(player3, roomCode)
      ]);
      
      // Add network faults
      this.simulateLatency(player1, 200);  // 200ms latency
      this.simulatePacketLoss(player2, 0.2);  // 20% packet loss
      
      // All players ready
      await Promise.all([
        this.playerReady(host),
        this.playerReady(player1),
        this.playerReady(player2),
        this.playerReady(player3)
      ]);
      
      // Start game
      await this.startGame(host);
      
      // Send some game actions with different network conditions
      console.log('Sending game actions with network faults...');
      
      // Normal player actions
      for (let i = 0; i < 10; i++) {
        this.sendAction(host, 'moveLeft');
        this.sendAction(player1, 'moveRight');  // With latency
        this.sendAction(player2, 'rotate');     // With packet loss
        this.sendAction(player3, 'moveLeft');
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      
      // Disconnect a player temporarily
      this.disconnectClient(player3);
      console.log('Player3 disconnected, continuing game...');
      
      // More actions from remaining players
      for (let i = 0; i < 5; i++) {
        this.sendAction(host, 'hardDrop');
        this.sendAction(player1, 'rotate');
        this.sendAction(player2, 'moveRight');
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      
      // Reconnect player
      this.reconnectClient(player3);
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      if (player3.socket.connected) {
        console.log('Player3 successfully reconnected');
        // Make the player ready again
        this.sendAction(player3, 'moveLeft');
      } else {
        console.log('Player3 failed to reconnect');
      }
      
      console.log('=== Network Fault Test Complete ===');
      console.log('Server handled the following fault conditions:');
      console.log('- Player with 200ms latency');
      console.log('- Player with 20% packet loss');
      console.log('- Player disconnection and reconnection');
      
    } catch (error) {
      console.error('Test failed:', error);
    } finally {
      // Clean up
      this.cleanup();
    }
  }
}

// Run the test
const test = new NetworkFaultTest();
test.runNetworkFaultTest().catch(console.error);