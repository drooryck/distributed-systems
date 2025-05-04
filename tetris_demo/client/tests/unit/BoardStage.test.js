import React from 'react';
import { render, screen } from '@testing-library/react';
import BoardStage from '../../src/BoardStage';

// Mock Konva
jest.mock('react-konva', () => ({
  Stage: ({ children, width, height }) => (
    <div data-testid="mock-stage" style={{ width, height }}>
      {children}
    </div>
  ),
  Layer: ({ children }) => <div data-testid="mock-layer">{children}</div>,
  Group: ({ children, x, y, opacity }) => (
    <div data-testid="mock-group" style={{ transform: `translate(${x}px, ${y}px)`, opacity }}>
      {children}
    </div>
  ),
  Rect: props => <div data-testid="mock-rect" data-props={JSON.stringify(props)} />,
}));

// Mock Audio
window.HTMLMediaElement.prototype.load = jest.fn();
window.HTMLMediaElement.prototype.play = jest.fn(() => Promise.resolve());

describe('BoardStage Component', () => {
  const defaultProps = {
    board: Array(20).fill().map(() => Array(10).fill(0)),
    players: {},
    linesToClear: [],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders with correct dimensions', () => {
    render(<BoardStage {...defaultProps} />);
    
    const stage = screen.getByTestId('mock-stage');
    const cellSize = 30; // From the CELL constant in the component
    
    expect(stage.style.width).toBe(`${10 * cellSize}px`);
    expect(stage.style.height).toBe(`${20 * cellSize}px`);
  });

  test('renders locked blocks from board data', () => {
    // Create a board with one locked block
    const boardWithBlock = [...defaultProps.board];
    boardWithBlock[19][0] = { value: 1 }; // I tetromino at bottom left
    
    render(<BoardStage board={boardWithBlock} players={defaultProps.players} linesToClear={[]} />);
    
    // With our mocking, we need to count the number of "mock-group" elements
    // that would contain blocks (we'll have one per board block + grid lines + active pieces)
    const groups = screen.getAllByTestId('mock-group');
    
    // One block + a group for grid lines 
    expect(groups.length).toBeGreaterThan(1);
  });

  test('renders active tetromino for player', () => {
    // Create a player with an active piece
    const players = {
      player1: {
        id: 'p1',
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
        isWaitingForNextPiece: false
      }
    };
    
    render(<BoardStage {...defaultProps} players={players} />);
    
    // Count blocks - should be 4 active blocks (O tetromino)
    const groups = screen.getAllByTestId('mock-group');
    
    // Grid lines + 4 blocks for tetromino
    expect(groups.length).toBeGreaterThan(4);
  });

  test('does not render tetromino if player is waiting for next piece', () => {
    // Create a player with an active piece but waiting flag is true
    const players = {
      player1: {
        id: 'p1',
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
        isWaitingForNextPiece: true
      }
    };
    
    render(<BoardStage {...defaultProps} players={players} />);
    
    // Only grid lines group should be present, no blocks
    const groups = screen.getAllByTestId('mock-group');
    
    // Just 1 group for grid lines, no player pieces
    expect(groups.length).toBeLessThan(5);
  });

  test('creates particles when lines are being cleared', () => {
    // Set up a board with a complete line and the line marked for clearing
    const boardWithFullLine = [...defaultProps.board];
    for (let i = 0; i < 10; i++) {
      boardWithFullLine[19][i] = { value: 1 }; // Fill bottom row
    }
    
    // First render without lines to clear
    const { rerender } = render(<BoardStage board={boardWithFullLine} players={defaultProps.players} linesToClear={[]} />);
    
    // Then render with line to clear
    rerender(<BoardStage board={boardWithFullLine} players={defaultProps.players} linesToClear={[19]} />);
    
    // Check sound was attempted to be played
    expect(window.HTMLMediaElement.prototype.play).toHaveBeenCalled();
    
    // There should be particle elements
    const rects = screen.getAllByTestId('mock-rect');
    const particleRects = rects.filter(rect => {
      const props = JSON.parse(rect.getAttribute('data-props') || '{}');
      return props.id && props.id.startsWith('p-');
    });
    
    expect(particleRects.length).toBeGreaterThan(0);
  });
  
  test('renders correctly with empty input', () => {
    // Test handling of potential edge cases with empty data
    const { container } = render(<BoardStage board={[]} players={{}} linesToClear={[]} />);
    
    // Should render without crashing
    expect(container).toBeDefined();
  });
});