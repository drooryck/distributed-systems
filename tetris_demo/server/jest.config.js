module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/__tests__/**/*.js?(x)', '**/?(*.)+(spec|test).js?(x)', '**/tests/**/*.js?(x)'],
  coveragePathIgnorePatterns: ['/node_modules/', '/tests/'],
  testTimeout: 30000, // Some tests might take longer due to simulating network conditions
  setupFilesAfterEnv: ['./tests/setup.js'],
  verbose: true
};