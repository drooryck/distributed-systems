import { renderHook, act } from '@testing-library/react';
import { saveGameSession, getGameSession, clearGameSession } from '../../src/utils/sessionStorage';
import useGameSession from '../../src/hooks/useGameSession';

// Mock the localStorage
const mockLocalStorage = (() => {
  let store = {};
  return {
    getItem: jest.fn(key => store[key] || null),
    setItem: jest.fn((key, value) => {
      store[key] = value.toString();
    }),
    removeItem: jest.fn(key => {
      delete store[key];
    }),
    clear: jest.fn(() => {
      store = {};
    })
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage
});

// Mock socket.io-client
jest.mock('socket.io-client', () => {
  const mockSocket = {
    on: jest.fn(),
    emit: jest.fn(),
    off: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    id: 'test-socket-id',
    connected: true
  };
  
  return jest.fn(() => mockSocket);
});

describe('Game Session Hooks', () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    jest.clearAllMocks();
  });
  
  test('saveGameSession saves data to localStorage', () => {
    const sessionData = {
      roomCode: 'TEST01',
      playerName: 'TestPlayer',
      socketId: 'socket123'
    };
    
    saveGameSession(sessionData);
    
    // Check that setItem was called
    expect(mockLocalStorage.setItem).toHaveBeenCalled();
    
    // Get the actual data that was saved
    const callArgs = mockLocalStorage.setItem.mock.calls[0];
    const [key, serializedValue] = callArgs;
    const parsedValue = JSON.parse(serializedValue);
    
    // Verify the key is correct
    expect(key).toBe('tetrisGameSession');
    
    // Verify the saved data contains our original values
    expect(parsedValue.roomCode).toBe(sessionData.roomCode);
    expect(parsedValue.playerName).toBe(sessionData.playerName);
    expect(parsedValue.socketId).toBe(sessionData.socketId);
    
    // Also verify timestamp was added
    expect(parsedValue.timestamp).toBeDefined();
  });
  
  test('getGameSession retrieves data from localStorage', () => {
    const sessionData = {
      roomCode: 'TEST01',
      playerName: 'TestPlayer',
      socketId: 'socket123'
    };
    
    // Setup localStorage with session data
    mockLocalStorage.setItem('tetrisGameSession', JSON.stringify(sessionData));
    
    const result = getGameSession();
    
    expect(mockLocalStorage.getItem).toHaveBeenCalledWith('tetrisGameSession');
    expect(result).toEqual(sessionData);
  });
  
  test('getGameSession returns null when no data exists', () => {
    const result = getGameSession();
    
    expect(mockLocalStorage.getItem).toHaveBeenCalledWith('tetrisGameSession');
    expect(result).toBeNull();
  });
  
  test('clearGameSession removes data from localStorage', () => {
    // Setup localStorage with session data
    mockLocalStorage.setItem('tetrisGameSession', JSON.stringify({
      roomCode: 'TEST01',
      playerName: 'TestPlayer',
      socketId: 'socket123'
    }));
    
    clearGameSession();
    
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('tetrisGameSession');
  });
  
  test('handles invalid JSON in localStorage', () => {
    // Setup localStorage with invalid JSON
    mockLocalStorage.setItem('tetrisGameSession', 'not-valid-json');
    
    const result = getGameSession();
    
    expect(result).toBeNull();
  });
});

describe('useGameSession Hook', () => {
  let mockSocket;
  
  beforeEach(() => {
    // Clear all mocks between tests
    jest.clearAllMocks();
    
    // Get the mocked socket instance
    mockSocket = require('socket.io-client')();
    
    // Default mock implementations for common socket events
    mockSocket.on.mockImplementation((event, callback) => {
      if (event === 'connect') {
        callback();
      }
      return mockSocket;
    });
  });

  test('should connect to the socket server', () => {
    const { result } = renderHook(() => useGameSession());
    
    // Check if socket.io-client was called with the correct URL
    expect(require('socket.io-client')).toHaveBeenCalled();
    
    // Check if the socket event listeners were registered
    expect(mockSocket.on).toHaveBeenCalledWith('connect', expect.any(Function));
    expect(mockSocket.on).toHaveBeenCalledWith('disconnect', expect.any(Function));
  });

  test('should handle room creation', () => {
    const { result } = renderHook(() => useGameSession());
    
    // Simulate creating a room
    act(() => {
      result.current.createRoom('TestPlayer');
    });
    
    // Check if the correct event was emitted
    expect(mockSocket.emit).toHaveBeenCalledWith('createRoom', 'TestPlayer');
  });

  test('should handle joining a room', () => {
    const { result } = renderHook(() => useGameSession());
    
    // Simulate joining a room
    act(() => {
      result.current.joinRoom('ABC123', 'TestPlayer');
    });
    
    // Check if the correct event was emitted
    expect(mockSocket.emit).toHaveBeenCalledWith('joinRoom', {
      roomCode: 'ABC123',
      playerName: 'TestPlayer'
    });
  });

  test('should mark player as ready', () => {
    const { result } = renderHook(() => useGameSession());
    
    // Set the roomCode in the state
    act(() => {
      // Simulate the room being created/joined
      result.current.setRoomCode('ABC123');
    });
    
    // Simulate player becoming ready
    act(() => {
      result.current.setReady();
    });
    
    // Check if the correct event was emitted
    expect(mockSocket.emit).toHaveBeenCalledWith('playerReady', { roomCode: 'ABC123' });
  });

  test('should handle starting the game', () => {
    const { result } = renderHook(() => useGameSession());
    
    // Set the roomCode in the state
    act(() => {
      // Simulate the room being created/joined
      result.current.setRoomCode('ABC123');
    });
    
    // Simulate starting the game
    act(() => {
      result.current.startGame();
    });
    
    // Check if the correct event was emitted
    expect(mockSocket.emit).toHaveBeenCalledWith('startGame', { roomCode: 'ABC123' });
  });
});