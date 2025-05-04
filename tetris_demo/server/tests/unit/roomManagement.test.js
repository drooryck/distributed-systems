// Tests for room management functionality
const server = require('../../src/server');

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

// Import the modules so mocks are applied
const { generateRoomCode, createRoom, leaveRoom, startGame, resetRoom } = server;

// Mock the rooms object directly in the server module
jest.mock('../../src/server', () => {
  const originalModule = jest.requireActual('../../src/server');
  return {
    ...originalModule,
    rooms: {},
    io: {
      to: jest.fn().mockReturnThis(),
      emit: jest.fn()
    },
    sockets: {
      adapter: {
        rooms: new Map()
      }
    }
  };
});

describe('Room Management Functions', () => {
  beforeEach(() => {
    // Reset mocks and room data before each test
    jest.clearAllMocks();
    
    // Clear rooms between tests
    for (const key in server.rooms) {
      delete server.rooms[key];
    }
    
    // Reset any function mocks
    if (server.io && server.io.to.mockClear) {
      server.io.to.mockClear();
      server.io.emit.mockClear();
    }
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
      expect(server.rooms).toHaveProperty(roomCode);
      expect(server.rooms[roomCode].gameState.appPhase).toBe('readyscreen');
      expect(server.rooms[roomCode].gameState.players[socketId].isHost).toBe(true);
      expect(server.rooms[roomCode].gameState.players[socketId].name).toBe('TestPlayer');
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
      
      // Set up our mock socket adapter rooms
      server.io.sockets = {
        adapter: {
          rooms: new Map([[roomCode, new Set([socketId])]])
        }
      };
      
      // Leave the room
      leaveRoom(mockSocket);
      
      // Verify player was removed
      expect(server.rooms[roomCode].gameState.activePlayers.has(socketId)).toBe(false);
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
      server.rooms[roomCode].gameState.players[playerId] = {
        id: playerId.substring(0, 4),
        isHost: false,
        playerNumber: 2,
        name: 'PlayerTwo'
      };
      server.rooms[roomCode].gameState.activePlayers.add(playerId);
      mockPlayer.roomCode = roomCode;
      
      // Set up our mock socket adapter rooms
      server.io.sockets = {
        adapter: {
          rooms: new Map([[roomCode, new Set([hostId, playerId])]])
        }
      };
      
      // Host leaves
      leaveRoom(mockHost);
      
      // Check new host assignment
      expect(server.rooms[roomCode].gameState.players[playerId].isHost).toBe(true);
    });
  });
});