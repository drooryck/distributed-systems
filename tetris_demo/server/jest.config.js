module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.js'],
  coveragePathIgnorePatterns: ['/node_modules/', '/tests/'],
  testTimeout: 30000,
  setupFilesAfterEnv: ['./tests/setup.js'],
  verbose: true
};
