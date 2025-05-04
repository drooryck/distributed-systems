import { act, renderHook } from '@testing-library/react-hooks';
import io from 'socket.io-client';

// Mock socket.io-client
jest.mock('socket.io-client', () => {
  const mockOn = jest.fn();
  const mockEmit = jest.fn();
  const mockConnect = jest.fn();
  const mockDisconnect = jest.fn();
  
  return jest.fn(() => ({
    on: mockOn,
    emit: mockEmit,
    connect: mockConnect,
    disconnect: mockDisconnect,
    id: 'mock-socket-id',
    connected: true
  }));
});

// Create a simple hook that wraps socket.io functionality for testing
const useSocketIntegration = () => {
  const socket = io('http://localhost:3000');
  
  const createRoom = (playerName) => {
    socket.emit('createRoom', playerName);
  };
  
  const joinRoom = (roomCode, playerName) => {
    socket.emit('joinRoom', { roomCode, playerName });
  };
  
  const playerReady = (roomCode) => {
    socket.emit('playerReady', { roomCode });
  };
  
  const startGame = (roomCode) => {
    socket.emit('startGame', { roomCode });
  };
  
  const sendPlayerAction = (action) => {
    socket.emit('playerAction', action);
  };
  
  const listenForEvents = (callback) => {
    socket.on('roomCreated', (data) => callback('roomCreated', data));
    socket.on('joinedRoom', (data) => callback('joinedRoom', data));
    socket.on('gameState', (data) => callback('gameState', data));
    socket.on('gameOver', (data) => callback('gameOver', data));
  };
  
  return {
    socket,
    createRoom,
    joinRoom,
    playerReady,
    startGame,
    sendPlayerAction,
    listenForEvents
  };
};

describe('Socket Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  test('connects to server and sets up event listeners', () => {
    const { result } = renderHook(() => useSocketIntegration());
    
    // Should have connected to the server
    expect(io).toHaveBeenCalledWith('http://localhost:3000');
    
    // Should register event listeners
    const { socket } = result.current;
    expect(socket.on).toHaveBeenCalledWith('roomCreated', expect.any(Function));
    expect(socket.on).toHaveBeenCalledWith('joinedRoom', expect.any(Function));
    expect(socket.on).toHaveBeenCalledWith('gameState', expect.any(Function));
    expect(socket.on).toHaveBeenCalledWith('gameOver', expect.any(Function));
  });
  
  test('emits createRoom event with player name', () => {
    const { result } = renderHook(() => useSocketIntegration());
    
    act(() => {
      result.current.createRoom('TestPlayer');
    });
    
    expect(result.current.socket.emit).toHaveBeenCalledWith('createRoom', 'TestPlayer');
  });
  
  test('emits joinRoom event with room code and player name', () => {
    const { result } = renderHook(() => useSocketIntegration());
    
    act(() => {
      result.current.joinRoom('ABC123', 'TestPlayer');
    });
    
    expect(result.current.socket.emit).toHaveBeenCalledWith('joinRoom', {
      roomCode: 'ABC123',
      playerName: 'TestPlayer'
    });
  });
  
  test('emits playerReady event with room code', () => {
    const { result } = renderHook(() => useSocketIntegration());
    
    act(() => {
      result.current.playerReady('ABC123');
    });
    
    expect(result.current.socket.emit).toHaveBeenCalledWith('playerReady', {
      roomCode: 'ABC123'
    });
  });
  
  test('emits startGame event with room code', () => {
    const { result } = renderHook(() => useSocketIntegration());
    
    act(() => {
      result.current.startGame('ABC123');
    });
    
    expect(result.current.socket.emit).toHaveBeenCalledWith('startGame', {
      roomCode: 'ABC123'
    });
  });
  
  test('emits playerAction event with action data', () => {
    const { result } = renderHook(() => useSocketIntegration());
    
    const action = { type: 'moveLeft', roomCode: 'ABC123' };
    
    act(() => {
      result.current.sendPlayerAction(action);
    });
    
    expect(result.current.socket.emit).toHaveBeenCalledWith('playerAction', action);
  });
  
  test('processes incoming events through callback', () => {
    const mockCallback = jest.fn();
    const { result } = renderHook(() => useSocketIntegration());
    
    act(() => {
      result.current.listenForEvents(mockCallback);
    });
    
    // Extract the event handlers
    const eventHandlers = {};
    const mockOn = result.current.socket.on;
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