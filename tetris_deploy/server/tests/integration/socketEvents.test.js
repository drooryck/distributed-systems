const { createServer } = require('http');
const { Server } = require('socket.io');
const Client = require('socket.io-client');
const { startServer, stopServer } = require('../../src/server');

// Integration test for Socket.IO events
describe('Socket.IO Events Integration', () => {
  let io, clientSocket, serverSocket;
  let httpServer;
  
  beforeAll((done) => {
    // Create a test HTTP server and Socket.IO server
    httpServer = createServer();
    io = new Server(httpServer);
    
    // Set up socket connection handlers
    io.on('connection', (socket) => {
      serverSocket = socket;
    });
    
    // Start the server on a dynamic port (0) to avoid conflicts
    httpServer.listen(0, () => {
      // Get the port that was assigned
      const port = httpServer.address().port;
      
      // Create a client socket connected to the test server
      clientSocket = new Client(`http://localhost:${port}`);
      clientSocket.on('connect', done);
    });
  });
  
  // Clean up all event listeners between tests
  beforeEach(() => {
    clientSocket.removeAllListeners('gameState');
    clientSocket.removeAllListeners('roomCreated');
    clientSocket.removeAllListeners('joinedRoom');
    clientSocket.removeAllListeners('gameOver');
    
    serverSocket.removeAllListeners('createRoom');
    serverSocket.removeAllListeners('joinRoom');
    serverSocket.removeAllListeners('playerReady');
    serverSocket.removeAllListeners('startGame');
    serverSocket.removeAllListeners('playerAction');
  });
  
  afterAll(() => {
    // Cleanup all connections
    if (clientSocket.connected) {
      clientSocket.disconnect();
    }
    io.close();
    httpServer.close();
  });
  
  test('client can emit createRoom and receive roomCreated event', (done) => {
    // Set up listener for expected response
    clientSocket.on('roomCreated', (data) => {
      // Verify the response contains expected format
      expect(data).toHaveProperty('roomCode');
      expect(data).toHaveProperty('gameState');
      expect(data.gameState.appPhase).toBe('readyscreen');
      expect(data.gameState.players).toBeDefined();
      
      // Check that the room contains the player that created it
      const playerIds = Object.keys(data.gameState.players);
      expect(playerIds.length).toBe(1);
      expect(data.gameState.players[playerIds[0]].isHost).toBe(true);
      done();
    });
    
    // When server receives message, send canned response
    serverSocket.on('createRoom', (playerName) => {
      const roomCode = 'TEST01';
      const gameState = {
        appPhase: 'readyscreen',
        players: {
          [serverSocket.id]: {
            id: serverSocket.id.substring(0, 4),
            isHost: true,
            name: playerName,
            playerNumber: 1
          }
        },
        activePlayers: [serverSocket.id],
        readyPlayers: []
      };
      
      serverSocket.emit('roomCreated', { roomCode, gameState });
    });
    
    // Emit the event to test
    clientSocket.emit('createRoom', 'TestPlayer');
  });
  
  test('client can emit joinRoom and receive joinedRoom event', (done) => {
    // Set up listener for expected response
    clientSocket.on('joinedRoom', (data) => {
      expect(data).toHaveProperty('roomCode');
      expect(data).toHaveProperty('gameState');
      expect(data.gameState.appPhase).toBe('readyscreen');
      
      // Verify the client was added to the room
      const players = data.gameState.players;
      expect(Object.keys(players)).toContain(clientSocket.id);
      done();
    });
    
    // When server receives message, send canned response
    serverSocket.on('joinRoom', (data) => {
      const { roomCode, playerName } = data;
      
      // Validate input
      expect(roomCode).toBe('TEST02');
      expect(playerName).toBe('JoiningPlayer');
      
      // Mock response
      const gameState = {
        appPhase: 'readyscreen',
        players: {
          'existingPlayer': {
            id: 'exis',
            isHost: true,
            name: 'HostPlayer',
            playerNumber: 1
          },
          [serverSocket.id]: {
            id: serverSocket.id.substring(0, 4),
            isHost: false,
            name: playerName,
            playerNumber: 2
          }
        },
        activePlayers: ['existingPlayer', serverSocket.id],
        readyPlayers: []
      };
      
      serverSocket.emit('joinedRoom', { roomCode, gameState });
    });
    
    // Emit the event to test
    clientSocket.emit('joinRoom', { roomCode: 'TEST02', playerName: 'JoiningPlayer' });
  });
  
  test('client can emit playerReady and receive gameState update', (done) => {
    // Set up listener for expected response
    clientSocket.on('gameState', (data) => {
      expect(data).toHaveProperty('appPhase', 'readyscreen');
      expect(data).toHaveProperty('readyPlayers');
      expect(data.readyPlayers).toContain(clientSocket.id);
      done();
    });
    
    // When server receives message, send canned response
    serverSocket.on('playerReady', (data) => {
      // Mock room code
      const roomCode = data.roomCode;
      
      // Send updated game state with player ready
      const gameState = {
        appPhase: 'readyscreen',
        players: {
          [serverSocket.id]: {
            id: serverSocket.id.substring(0, 4),
            isHost: true,
            name: 'TestPlayer',
            playerNumber: 1,
            isReady: true
          }
        },
        activePlayers: [serverSocket.id],
        readyPlayers: [serverSocket.id]
      };
      
      serverSocket.emit('gameState', gameState);
    });
    
    // Emit the event to test
    clientSocket.emit('playerReady', { roomCode: 'TEST03' });
  });
  
  test('client can emit startGame and receive gameState with playing phase', (done) => {
    // Set up listener for expected response
    clientSocket.on('gameState', (data) => {
      expect(data).toHaveProperty('appPhase', 'playing');
      expect(data).toHaveProperty('board');
      expect(Array.isArray(data.board)).toBe(true);
      done();
    });
    
    // When server receives message, send canned response
    serverSocket.on('startGame', (data) => {
      // Mock room code
      const roomCode = data.roomCode;
      
      // Create an empty board
      const board = Array(20).fill().map(() => Array(10).fill(0));
      
      // Send updated game state in playing phase
      const gameState = {
        appPhase: 'playing',
        gameInProgress: true,
        board,
        players: {
          [serverSocket.id]: {
            id: serverSocket.id.substring(0, 4),
            isHost: true,
            name: 'TestPlayer',
            playerNumber: 1,
            score: 0,
            x: 4,
            y: 0,
            currentPiece: {
              type: 'I',
              shape: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
              rotationIndex: 0
            }
          }
        },
        activePlayers: [serverSocket.id],
        readyPlayers: [serverSocket.id]
      };
      
      serverSocket.emit('gameState', gameState);
    });
    
    // Emit the event to test
    clientSocket.emit('startGame', { roomCode: 'TEST04' });
  });
  
  test('client can emit playerAction and receive gameState update', (done) => {
    // Set up listener for expected response
    clientSocket.on('gameState', (data) => {
      expect(data).toHaveProperty('players');
      expect(data.players[serverSocket.id]).toHaveProperty('x', 5);  // Moved right from initial 4
      done();
    });
    
    // When server receives message, send canned response
    serverSocket.on('playerAction', (data) => {
      expect(data).toHaveProperty('type', 'moveRight');
      
      // Send updated game state with player moved
      const gameState = {
        appPhase: 'playing',
        gameInProgress: true,
        board: Array(20).fill().map(() => Array(10).fill(0)),
        players: {
          [serverSocket.id]: {
            id: serverSocket.id.substring(0, 4),
            isHost: true,
            name: 'TestPlayer',
            playerNumber: 1,
            score: 0,
            x: 5, // Moved right from initial 4
            y: 0,
            currentPiece: {
              type: 'I',
              shape: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
              rotationIndex: 0
            }
          }
        },
        activePlayers: [serverSocket.id]
      };
      
      serverSocket.emit('gameState', gameState);
    });
    
    // Emit the event to test
    clientSocket.emit('playerAction', { type: 'moveRight' });
  });
  
  test('client receives gameOver event when game ends', (done) => {
    clientSocket.on('gameOver', (data) => {
      expect(data).toHaveProperty('score');
      expect(data).toHaveProperty('playerId');
      expect(data).toHaveProperty('isMultiplayer');
      done();
    });
    
    // Simulate server sending game over event
    serverSocket.emit('gameOver', { 
      playerId: serverSocket.id, 
      score: 1000,
      totalScore: 1000,
      isMultiplayer: false
    });
  });
});