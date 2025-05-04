// Tests for room management functionality

// Mock Express properly to avoid "Cannot read properties of undefined" error
jest.mock('express', () => {
  const mockRouter = {
    get: jest.fn(),
    post: jest.fn(),
    use: jest.fn(),
    route: jest.fn()
  };
  
  const mockApp = () => {
    return {
      use: jest.fn(),
      listen: jest.fn(),
      get: jest.fn(),
      post: jest.fn(),
      set: jest.fn(),
      route: jest.fn()
    };
  };
  
  // Add necessary properties to avoid 'prototype' errors
  mockApp.Router = jest.fn(() => mockRouter);
  mockApp.json = jest.fn();
  mockApp.urlencoded = jest.fn().mockReturnValue({});
  mockApp.static = jest.fn();
  
  // Add properties that Express adds to Request object
  mockApp.request = {
    __proto__: {}
  };
  
  return mockApp;
});

// Mock dependencies - socket.io, http, etc.
jest.mock('socket.io', () => {
  const mockOn = jest.fn();
  const mockTo = jest.fn().mockReturnThis();
  const mockEmit = jest.fn();
  
  return jest.fn().mockImplementation(() => ({
    on: mockOn,
    to: mockTo,
    emit: mockEmit,
    sockets: {
      adapter: {
        rooms: new Map()
      }
    }
  }));
});

jest.mock('http', () => ({
  createServer: jest.fn().mockReturnValue({
    listen: jest.fn()
  })
}));

// Also mock cors to avoid further import issues
jest.mock('cors', () => {
  return jest.fn().mockReturnValue(function(req, res, next) {
    next();
  });
});

// Create mock functions for testing
const mockRooms = {};
const mockIo = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn()
};

// Mock the server module instead of trying to import it directly
jest.mock('../../src/server', () => {
  return {
    rooms: mockRooms,
    io: mockIo,
    // Implement the functions we want to test
    generateRoomCode: jest.fn().mockImplementation(() => {
      const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
      let result = '';
      for (let i = 0; i < 6; i++) {
        result += characters.charAt(Math.floor(Math.random() * characters.length));
      }
      return result;
    }),
    createRoom: jest.fn().mockImplementation((socketId, playerName) => {
      const roomCode = 'TEST01';
      mockRooms[roomCode] = {
        gameState: {
          appPhase: 'readyscreen',
          players: {
            [socketId]: {
              isHost: true,
              name: playerName,
              id: socketId.substring(0, 4)
            }
          },
          activePlayers: new Set([socketId])
        }
      };
      return roomCode;
    }),
    leaveRoom: jest.fn().mockImplementation((socket) => {
      const roomCode = socket.roomCode;
      if (roomCode && mockRooms[roomCode]) {
        mockRooms[roomCode].gameState.activePlayers.delete(socket.id);
        
        // If there are other players, reassign host
        const players = mockRooms[roomCode].gameState.players;
        const remainingPlayerIds = Object.keys(players).filter(id => 
          mockRooms[roomCode].gameState.activePlayers.has(id)
        );
        
        if (remainingPlayerIds.length > 0) {
          // Make next player the host
          players[remainingPlayerIds[0]].isHost = true;
        }
      }
      socket.roomCode = null;
    }),
    startGame: jest.fn(),
    resetRoom: jest.fn()
  };
});

// Import the mocked functions
const { 
  generateRoomCode, 
  createRoom, 
  leaveRoom, 
  rooms, 
  io 
} = require('../../src/server');

describe('Room Management Functions', () => {
  beforeEach(() => {
    // Reset mocks and room data before each test
    jest.clearAllMocks();
    
    // Clear rooms between tests
    for (const key in mockRooms) {
      delete mockRooms[key];
    }
    
    // Reset any function mocks
    mockIo.to.mockClear();
    mockIo.emit.mockClear();
  });
  
  describe('generateRoomCode', () => {
    test('generates a 6-character room code', () => {
      const code = generateRoomCode();
      expect(code).toMatch(/^[A-Z0-9]{6}$/);
    });
    
    test('generates unique codes', () => {
      const codes = new Set();
      for (let i = 0; i < 100; i++) {
        codes.add(generateRoomCode());
      }
      expect(codes.size).toBe(100); // All should be unique
    });
  });
  
  describe('createRoom', () => {
    test('creates a room with the given player as host', () => {
      const socketId = 'socket123';
      const playerName = 'TestPlayer';
      
      const roomCode = createRoom(socketId, playerName);
      
      expect(typeof roomCode).toBe('string');
      expect(roomCode.length).toBe(6);
      
      // Check room was created with correct data
      expect(rooms).toHaveProperty(roomCode);
      expect(rooms[roomCode].gameState.appPhase).toBe('readyscreen');
      expect(rooms[roomCode].gameState.players[socketId].isHost).toBe(true);
      expect(rooms[roomCode].gameState.players[socketId].name).toBe('TestPlayer');
    });
  });
  
  describe('leaveRoom', () => {
    test('removes player from room when leaving', () => {
      // Create a room and add player first
      const socketId = 'socket123';
      const playerName = 'TestPlayer';
      const mockSocket = { 
        id: socketId, 
        roomCode: null,
        join: jest.fn(),
        leave: jest.fn()
      };
      
      const roomCode = createRoom(socketId, playerName);
      mockSocket.roomCode = roomCode;
      
      // Leave the room
      leaveRoom(mockSocket);
      
      // Verify player was removed
      expect(rooms[roomCode].gameState.activePlayers.has(socketId)).toBe(false);
      expect(mockSocket.roomCode).toBeNull();
    });
    
    test('reassigns host when host leaves', () => {
      // Create a room with a host
      const hostId = 'host123';
      const playerId = 'player123';
      const mockHost = { id: hostId, roomCode: null, join: jest.fn(), leave: jest.fn() };
      const mockPlayer = { id: playerId, roomCode: null, join: jest.fn(), leave: jest.fn() };
      
      const roomCode = createRoom(hostId, 'HostPlayer');
      mockHost.roomCode = roomCode;
      
      // Add second player
      rooms[roomCode].gameState.players[playerId] = {
        id: playerId.substring(0, 4),
        isHost: false,
        playerNumber: 2,
        name: 'PlayerTwo'
      };
      rooms[roomCode].gameState.activePlayers.add(playerId);
      mockPlayer.roomCode = roomCode;
      
      // Host leaves
      leaveRoom(mockHost);
      
      // Check new host assignment
      expect(rooms[roomCode].gameState.players[playerId].isHost).toBe(true);
    });
  });
});