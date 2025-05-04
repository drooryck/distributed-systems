import io from 'socket.io-client';

// Mock socket.io-client
jest.mock('socket.io-client', () => {
  const mockOn = jest.fn();
  const mockEmit = jest.fn();
  const mockOnce = jest.fn();
  const mockConnect = jest.fn();
  const mockDisconnect = jest.fn();
  
  return jest.fn(() => ({
    on: mockOn,
    emit: mockEmit,
    once: mockOnce,
    connect: mockConnect,
    disconnect: mockDisconnect,
    id: 'mock-socket-id',
    connected: true
  }));
});

// Create a socket communication class for testing
class SocketCommunication {
  constructor() {
    this.socket = io('http://localhost:3001');
  }
  
  createRoom(playerName) {
    this.socket.emit('createRoom', playerName);
  }
  
  joinRoom(roomCode, playerName) {
    this.socket.emit('joinRoom', { roomCode, playerName });
  }
  
  playerReady(roomCode) {
    this.socket.emit('playerReady', { roomCode });
  }
  
  startGame(roomCode) {
    this.socket.emit('startGame', { roomCode });
  }
  
  sendPlayerAction(action) {
    this.socket.emit('playerAction', action);
  }
  
  listenForEvents(callback) {
    this.socket.on('roomCreated', (data) => callback('roomCreated', data));
    this.socket.on('joinedRoom', (data) => callback('joinedRoom', data));
    this.socket.on('gameState', (data) => callback('gameState', data));
    this.socket.on('gameOver', (data) => callback('gameOver', data));
    
    return () => {
      this.socket.disconnect();
    };
  }
}

describe('Socket Integration Tests', () => {
  let socketComm;
  
  beforeEach(() => {
    jest.clearAllMocks();
    socketComm = new SocketCommunication();
  });
  
  test('connects to server', () => {
    // Should have connected to the server
    expect(io).toHaveBeenCalledWith('http://localhost:3001');
  });
  
  test('registers event listeners', () => {
    // Create a mock callback
    const mockCallback = jest.fn();
    
    // Register event listeners
    socketComm.listenForEvents(mockCallback);
    
    // Should register event listeners
    const { socket } = socketComm;
    expect(socket.on).toHaveBeenCalledWith('roomCreated', expect.any(Function));
    expect(socket.on).toHaveBeenCalledWith('joinedRoom', expect.any(Function));
    expect(socket.on).toHaveBeenCalledWith('gameState', expect.any(Function));
    expect(socket.on).toHaveBeenCalledWith('gameOver', expect.any(Function));
  });
  
  test('emits createRoom event with player name', () => {
    socketComm.createRoom('TestPlayer');
    expect(socketComm.socket.emit).toHaveBeenCalledWith('createRoom', 'TestPlayer');
  });
  
  test('emits joinRoom event with room code and player name', () => {
    socketComm.joinRoom('ABC123', 'TestPlayer');
    expect(socketComm.socket.emit).toHaveBeenCalledWith('joinRoom', {
      roomCode: 'ABC123',
      playerName: 'TestPlayer'
    });
  });
  
  test('emits playerReady event with room code', () => {
    socketComm.playerReady('ABC123');
    expect(socketComm.socket.emit).toHaveBeenCalledWith('playerReady', {
      roomCode: 'ABC123'
    });
  });
  
  test('emits startGame event with room code', () => {
    socketComm.startGame('ABC123');
    expect(socketComm.socket.emit).toHaveBeenCalledWith('startGame', {
      roomCode: 'ABC123'
    });
  });
  
  test('emits playerAction event with action data', () => {
    const action = { type: 'moveLeft', roomCode: 'ABC123' };
    socketComm.sendPlayerAction(action);
    expect(socketComm.socket.emit).toHaveBeenCalledWith('playerAction', action);
  });
  
  test('processes incoming events through callback', () => {
    const mockCallback = jest.fn();
    
    // Register event listeners
    socketComm.listenForEvents(mockCallback);
    
    // Extract the event handlers
    const eventHandlers = {};
    const mockOn = socketComm.socket.on;
    mockOn.mock.calls.forEach(call => {
      const [event, handler] = call;
      eventHandlers[event] = handler;
    });
    
    // Simulate receiving an event
    const mockRoomData = { roomCode: 'ABC123', gameState: { players: {} } };
    eventHandlers.roomCreated(mockRoomData);
    
    expect(mockCallback).toHaveBeenCalledWith('roomCreated', mockRoomData);
  });
});