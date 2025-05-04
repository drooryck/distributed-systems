const { createServer } = require('http');
const { Server } = require('socket.io');
const Client = require('socket.io-client');
const { startServer, stopServer } = require('../../src/server');

// Mock the cluster manager
jest.mock('../../src/clusterManager', () => {
  return jest.fn().mockImplementation(() => ({
    initialize: jest.fn(),
    isLeaderServer: () => true,
    on: jest.fn()
  }));
});

// Integration test for full game flow
describe('Game Flow Integration', () => {
  let clientSockets = [];
  let serverSocket;
  let io;
  let httpServer;
  
  beforeAll((done) => {
    // Create a test HTTP server and Socket.IO server
    httpServer = createServer();
    io = new Server(httpServer);
    
    // Set up server connection handler
    io.on('connection', (socket) => {
      serverSocket = socket;
    });
    
    // Start the server
    httpServer.listen(() => {
      // Get the port that was assigned
      const port = httpServer.address().port;
      done();
    });
  });
  
  afterAll(() => {
    // Cleanup all connections
    io.close();
    clientSockets.forEach(socket => socket.close());
    httpServer.close();
  });
  
  beforeEach(() => {
    // Reset client sockets before each test
    clientSockets.forEach(socket => socket.close());
    clientSockets = [];
  });
  
  // Helper function to create a new client socket
  const createClientSocket = () => {
    const socket = Client(`http://localhost:${httpServer.address().port}`);
    clientSockets.push(socket);
    return socket;
  };
  
  // Helper function to wait for a socket event
  const waitForEvent = (socket, event) => {
    return new Promise((resolve) => {
      socket.once(event, (data) => {
        resolve(data);
      });
    });
  };
  
  test('complete game flow from room creation to game over', async () => {
    // Create host socket
    const hostSocket = createClientSocket();
    await new Promise(resolve => hostSocket.on('connect', resolve));
    
    // Create room
    hostSocket.emit('createRoom', 'HostPlayer');
    const roomCreatedData = await waitForEvent(hostSocket, 'roomCreated');
    
    // Validate room creation
    expect(roomCreatedData).toHaveProperty('roomCode');
    expect(roomCreatedData).toHaveProperty('gameState');
    expect(roomCreatedData.gameState.appPhase).toBe('readyscreen');
    
    const roomCode = roomCreatedData.roomCode;
    
    // Connect second player
    const player2Socket = createClientSocket();
    await new Promise(resolve => player2Socket.on('connect', resolve));
    
    // Join room
    player2Socket.emit('joinRoom', { roomCode, playerName: 'Player2' });
    const joinedRoomData = await waitForEvent(player2Socket, 'joinedRoom');
    
    // Validate room join
    expect(joinedRoomData).toHaveProperty('roomCode', roomCode);
    expect(joinedRoomData.gameState.appPhase).toBe('readyscreen');
    
    // Both players ready up
    hostSocket.emit('playerReady', { roomCode });
    player2Socket.emit('playerReady', { roomCode });
    
    // Wait for both readyPlayer events
    await waitForEvent(hostSocket, 'gameState');
    await waitForEvent(player2Socket, 'gameState');
    
    // Host starts the game
    hostSocket.emit('startGame', { roomCode });
    
    // Both players should receive gameState update with playing phase
    const hostGameState = await waitForEvent(hostSocket, 'gameState');
    const player2GameState = await waitForEvent(player2Socket, 'gameState');
    
    expect(hostGameState.appPhase).toBe('playing');
    expect(player2GameState.appPhase).toBe('playing');
    
    // Simulate some gameplay actions
    hostSocket.emit('playerAction', { type: 'moveRight' });
    player2Socket.emit('playerAction', { type: 'moveLeft' });
    
    // Wait for game state updates
    await waitForEvent(hostSocket, 'gameState');
    await waitForEvent(player2Socket, 'gameState');
    
    hostSocket.emit('playerAction', { type: 'hardDrop' });
    await waitForEvent(hostSocket, 'gameState');
    
    // Simulate game over (this would typically be triggered by server)
    io.to(roomCode).emit('gameOver', {
      playerId: hostSocket.id,
      score: 1000,
      totalScore: 1200,
      isMultiplayer: true
    });
    
    // Check that both players receive game over event
    const hostGameOverData = await waitForEvent(hostSocket, 'gameOver');
    const player2GameOverData = await waitForEvent(player2Socket, 'gameOver');
    
    expect(hostGameOverData).toHaveProperty('score');
    expect(hostGameOverData).toHaveProperty('totalScore');
    expect(player2GameOverData).toHaveProperty('score');
    
    // Check room reset after game over
    await waitForEvent(hostSocket, 'gameState');
    await waitForEvent(player2Socket, 'gameState');
    
    // Player leaves
    player2Socket.emit('leaveRoom');
    const leaveRoomEvent = await waitForEvent(player2Socket, 'roomLeft');
    expect(leaveRoomEvent).toBeDefined();
  }, 10000); // Increase timeout for this test
});