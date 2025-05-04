// Global test setup for server tests

// Increase timeout for all tests
jest.setTimeout(10000);

// Mock console methods to reduce noise in test output
global.originalConsole = {
  log: console.log,
  error: console.error,
  warn: console.warn,
  info: console.info,
  debug: console.debug
};

// Comment this section to see console output during tests
if (process.env.TEST_VERBOSE !== 'true') {
  console.log = jest.fn();
  console.error = jest.fn();
  console.warn = jest.fn();
  console.info = jest.fn();
  console.debug = jest.fn();
}

// Global helper to restore console methods
global.restoreConsole = () => {
  console.log = global.originalConsole.log;
  console.error = global.originalConsole.error;
  console.warn = global.originalConsole.warn;
  console.info = global.originalConsole.info;
  console.debug = global.originalConsole.debug;
};

// Global helper for Socket.IO mocking
global.createSocketIOServerMock = () => {
  const mockOn = jest.fn();
  const mockTo = jest.fn().mockReturnThis();
  const mockEmit = jest.fn();
  
  return {
    on: mockOn,
    to: mockTo,
    emit: mockEmit,
    sockets: {
      adapter: {
        rooms: new Map()
      }
    }
  };
};

// Clean up after all tests
afterAll(() => {
  // Restore console
  global.restoreConsole();
});