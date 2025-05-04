module.exports = {
  // Automatically clear mock calls and instances between every test
  clearMocks: true,
  
  // Indicates whether the coverage information should be collected while executing the test
  collectCoverage: false,

  // An array of glob patterns indicating a set of files for which coverage information should be collected
  collectCoverageFrom: [
    "src/**/*.{js,jsx}",
    "!src/**/*.d.ts",
    "!src/index.js",
    "!src/serviceWorker.js"
  ],

  // The directory where Jest should output its coverage files
  coverageDirectory: "coverage",

  // A list of paths to directories that Jest should use to search for test files
  roots: [
    "<rootDir>/src",
    "<rootDir>/tests"
  ],

  // The test environment that will be used for testing
  testEnvironment: "jsdom",

  // The glob patterns Jest uses to detect test files
  testMatch: [
    "**/__tests__/**/*.js?(x)",
    "**/?(*.)+(spec|test).js?(x)",
    "**/tests/**/*.test.js?(x)",
    "**/tests/e2e/**/*.test.js?(x)",
    "**/tests/e2e/**/*.spec.js?(x)"
  ],

  // A map from regular expressions to module names that allow to stub out resources with a single module
  moduleNameMapper: {
    "\\.(css|less|scss|sass)$": "<rootDir>/tests/__mocks__/styleMock.js",
    "\\.(gif|ttf|eot|svg|png)$": "<rootDir>/tests/__mocks__/fileMock.js"
  },

  // Setup files that will be run before each test
  setupFilesAfterEnv: [
    "<rootDir>/src/setupTests.js"
  ],
  
  // Transform files with babel-jest
  transform: {
    "^.+\\.(js|jsx|ts|tsx)$": "babel-jest"
  },
  
  // Tell Jest to handle ES modules
  transformIgnorePatterns: [
    "/node_modules/(?!(@testing-library|react-konva|konva)/)"
  ],
  
  // Set Jest to use an environment that supports ESM
  testEnvironmentOptions: {
    customExportConditions: ['node', 'node-addons']
  },

  // Indicate this is an ESM project - only including .jsx since .js is inferred
  extensionsToTreatAsEsm: ['.jsx'],

  // Indicates whether each individual test should be reported during the run
  verbose: true,
  
  // Increase timeout for e2e tests
  testTimeout: 30000
};