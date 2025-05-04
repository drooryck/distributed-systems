import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ReadyScreen from '../../../src/ReadyScreen';

describe('ReadyScreen Component', () => {
  const defaultProps = {
    players: {
      'player1': {
        id: 'play',
        name: 'Player 1',
        playerNumber: 1,
        isHost: true,
        color: '#00FFFF'
      },
      'player2': {
        id: 'play2',
        name: 'Player 2',
        playerNumber: 2,
        isHost: false,
        color: '#FFFF00'
      }
    },
    currentPlayerId: 'player1',
    readyPlayers: [],
    onReady: jest.fn(),
    onStartGame: jest.fn(),
    onLeaveRoom: jest.fn(),
    onSetGameMode: jest.fn(),
    gameMode: 'classic',
    gameInProgress: false,
    roomCode: 'TEST01'
  };

  test('renders the room code', () => {
    render(<ReadyScreen {...defaultProps} />);
    expect(screen.getByText(/TEST01/)).toBeInTheDocument();
  });

  test('renders player slots', () => {
    render(<ReadyScreen {...defaultProps} />);
    expect(screen.getByText('Player 1')).toBeInTheDocument();
    expect(screen.getByText('Player 2')).toBeInTheDocument();
  });

  test('displays host indicator for host player', () => {
    render(<ReadyScreen {...defaultProps} />);
    expect(screen.getByText('HOST')).toBeInTheDocument();
  });

  test('shows ready button for current player', () => {
    render(<ReadyScreen {...defaultProps} />);
    expect(screen.getByRole('button', { name: /READY!/i })).toBeInTheDocument();
  });

  test('clicking ready button triggers onReady', () => {
    render(<ReadyScreen {...defaultProps} />);
    
    const readyButton = screen.getByRole('button', { name: /READY!/i });
    fireEvent.click(readyButton);
    
    expect(defaultProps.onReady).toHaveBeenCalledWith(true);
  });

  test('host sees start game button', () => {
    render(<ReadyScreen {...defaultProps} />);
    expect(screen.getByRole('button', { name: /Start Game/i })).toBeInTheDocument();
  });

  test('non-host does not see start game button', () => {
    const nonHostProps = {
      ...defaultProps,
      currentPlayerId: 'player2'
    };
    
    render(<ReadyScreen {...nonHostProps} />);
    
    // Instead of start button, non-host sees waiting message
    expect(screen.queryByRole('button', { name: /Start Game/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Waiting for Host/i)).toBeInTheDocument();
  });

  test('host cannot start game when no players are ready', () => {
    render(<ReadyScreen {...defaultProps} />);
    
    const startButton = screen.getByRole('button', { name: /Start Game/i });
    fireEvent.click(startButton);
    
    // Start button should be disabled when no players are ready
    expect(defaultProps.onStartGame).not.toHaveBeenCalled();
  });

  test('host can start game when players are ready', () => {
    const propsWithReadyPlayers = {
      ...defaultProps,
      readyPlayers: ['player1', 'player2']
    };
    
    render(<ReadyScreen {...propsWithReadyPlayers} />);
    
    const startButton = screen.getByRole('button', { name: /Start Game/i });
    fireEvent.click(startButton);
    
    expect(defaultProps.onStartGame).toHaveBeenCalled();
  });

  test('shows leave room button', () => {
    render(<ReadyScreen {...defaultProps} />);
    
    const leaveButton = screen.getByRole('button', { name: /Leave Room/i });
    fireEvent.click(leaveButton);
    
    expect(defaultProps.onLeaveRoom).toHaveBeenCalled();
  });
});