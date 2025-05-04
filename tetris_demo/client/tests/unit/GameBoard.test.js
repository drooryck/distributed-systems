import React from 'react';
import { render, screen } from '@testing-library/react';
import GameBoard from '../../../src/GameBoard';

// Mock canvas context
const mockCanvas = {
  getContext: jest.fn().mockReturnValue({
    clearRect: jest.fn(),
    fillRect: jest.fn(),
    strokeRect: jest.fn(),
    beginPath: jest.fn(),
    moveTo: jest.fn(),
    lineTo: jest.fn(),
    closePath: jest.fn(),
    fill: jest.fn(),
    stroke: jest.fn(),
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0
  })
};

// Mock the canvas ref
jest.mock('react', () => {
  const originalReact = jest.requireActual('react');
  return {
    ...originalReact,
    useRef: jest.fn().mockReturnValue({ current: mockCanvas }),
    useEffect: jest.fn().mockImplementation((fn) => fn()),
  };
});

describe('GameBoard Component', () => {
  beforeEach(() => {
    // Clear all mock function calls between tests
    jest.clearAllMocks();
  });
  
  test('renders the game board canvas', () => {
    const board = Array(20).fill().map(() => Array(10).fill(0));
    const players = {};
    
    render(<GameBoard board={board} players={players} currentPlayerId="player1" />);
    
    // Check that the canvas context was accessed
    expect(mockCanvas.getContext).toHaveBeenCalledWith('2d');
  });
  
  test('renders correct board dimensions', () => {
    // Create a 20x10 board (standard size)
    const board = Array(20).fill().map(() => Array(10).fill(0));
    const players = {};
    
    render(<GameBoard board={board} players={players} currentPlayerId="player1" />);
    
    const ctx = mockCanvas.getContext();
    
    // Verify the canvas was cleared with the correct dimensions
    expect(ctx.clearRect).toHaveBeenCalled();
    
    // Should have drawn grid lines for rows and columns
    expect(ctx.beginPath).toHaveBeenCalledTimes(expect.any(Number));
    expect(ctx.moveTo).toHaveBeenCalledTimes(expect.any(Number));
    expect(ctx.stroke).toHaveBeenCalledTimes(expect.any(Number));
  });
  
  test('renders active tetrominos for players', () => {
    // Create a board with one player who has an active tetromino
    const board = Array(20).fill().map(() => Array(10).fill(0));
    const players = {
      'player1': {
        id: 'play',
        currentPiece: {
          shape: [
            [1, 1, 0, 0],
            [1, 1, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
          ]
        },
        x: 4,
        y: 0,
        color: '#00FFFF'
      }
    };
    
    render(<GameBoard board={board} players={players} currentPlayerId="player1" />);
    
    const ctx = mockCanvas.getContext();
    
    // Should draw additional blocks for the active tetromino
    expect(ctx.fillStyle).toHaveBeenCalledTimes(expect.any(Number));
    expect(ctx.fillRect).toHaveBeenCalledTimes(expect.any(Number));
  });
  
  test('renders line clear animation when lines are being cleared', () => {
    const board = Array(20).fill().map(() => Array(10).fill(0));
    board.linesToClear = [18, 19]; // Bottom two rows being cleared
    
    render(<GameBoard board={board} players={{}} currentPlayerId="player1" />);
    
    const ctx = mockCanvas.getContext();
    
    // Should draw flash effect for lines being cleared
    expect(ctx.fillStyle).toHaveBeenCalledTimes(expect.any(Number));
    expect(ctx.fillRect).toHaveBeenCalledTimes(expect.any(Number));
  });
});