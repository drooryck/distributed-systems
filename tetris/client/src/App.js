import React, { useEffect, useState, useCallback } from 'react';
import { io } from 'socket.io-client';
import GameBoard from './GameBoard';

// Add debugging to see connection attempts
console.log('Attempting to connect to server at http://localhost:3001');
const socket = io('http://localhost:3001'); // server endpoint

function App() {
  const [gameState, setGameState] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [playerList, setPlayerList] = useState([]);

  useEffect(() => {
    socket.on('connect', () => {
      console.log('Connected to server! My socket ID is:', socket.id);
      setConnectionStatus('connected');
    });
  
    socket.on('connect_error', (error) => {
      console.log('Connection error:', error);
      setConnectionStatus('error: ' + error.message);
    });

    socket.on('init', (data) => {
      console.log('Received init data:', data);
      setGameState(data);
      updatePlayerList(data.players);
    });
  
    socket.on('gameState', (data) => {
      console.log('Received gameState update:', data);
      setGameState(data);
      updatePlayerList(data.players);
    });
  
    // Cleanup event listeners when component unmounts
    return () => {
      socket.off('connect');
      socket.off('connect_error');
      socket.off('init');
      socket.off('gameState');
    };
  }, []);
  
  // Update the player list for display
  const updatePlayerList = useCallback((players) => {
    const list = Object.entries(players).map(([id, player]) => ({
      id: id.substring(0, 4),
      score: player.score,
      color: player.color,
      isCurrentPlayer: id === socket.id
    }));
    setPlayerList(list);
  }, []);
  
  // Handle keyboard input
  const handleKeyDown = useCallback((e) => {
    let action = null;
    let dasAction = null;
    
    switch (e.key) {
      case 'ArrowLeft':
        action = { type: 'moveLeft' };
        dasAction = { type: 'startDAS', direction: 'left' };
        break;
      case 'ArrowRight':
        action = { type: 'moveRight' };
        dasAction = { type: 'startDAS', direction: 'right' };
        break;
      case 'ArrowDown':
        action = { type: 'softDrop' }; // New action type
        break;
      case 'ArrowUp':
      case 'z':
      case 'Z':
        action = { type: 'rotate' };
        break;
      case ' ': // Space for hard drop
        action = { type: 'hardDrop' };
        break;
    }
  
    if (action) {
      socket.emit('playerAction', action);
      if (dasAction) {
        socket.emit('playerAction', dasAction);
      }
      e.preventDefault();
    }
  }, []);

const handleKeyUp = useCallback((e) => {
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    socket.emit('playerAction', { type: 'endDAS' });
  }
  if (e.key === 'ArrowDown') {
    socket.emit('playerAction', { type: 'endSoftDrop' });
  }
}, []);

  // Auto-focus the game div on mount and when game state changes
  useEffect(() => {
    const gameDiv = document.getElementById('game-area');
    if (gameDiv) {
      gameDiv.focus();
    }
  }, [gameState]);

  if (!gameState) {
    return (
      <div>
        <h1>Tetristributed</h1>
        <p>Connection status: {connectionStatus}</p>
        <p>Waiting for game state from server...</p>
      </div>
    );
  }

  return (
    <div 
      id="game-area"
      onKeyDown={handleKeyDown}
      onKeyUp={handleKeyUp} // Add the onKeyUp handler here
      tabIndex="0" 
      style={{ outline: 'none', display: 'flex', flexDirection: 'column', alignItems: 'center' }}
    >
      <h1>Tetristributed</h1>
      <p>Connected as player: {socket.id && socket.id.substring(0, 4)}</p>
      
      <div style={{ display: 'flex', gap: '20px', marginBottom: '20px' }}>
        <GameBoard 
          board={gameState.board} 
          players={gameState.players}
          currentPlayerId={socket.id}
        />
        
        <div style={{ minWidth: '200px' }}>
          <h2>Players</h2>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {playerList.map(player => (
              <li 
                key={player.id} 
                style={{ 
                  margin: '8px 0',
                  padding: '8px',
                  backgroundColor: player.isCurrentPlayer ? '#444' : '#333',
                  borderLeft: `4px solid ${player.color}`,
                  borderRadius: '4px'
                }}
              >
                Player {player.id} {player.isCurrentPlayer ? '(You)' : ''}: {player.score} points
              </li>
            ))}
          </ul>
          
          <div style={{ marginTop: '20px' }}>
            <h3>Controls</h3>
            <p>← → : Move left/right</p>
            <p>↑ or Z : Rotate</p>
            <p>↓ : Soft drop (hold)</p>
            <p>Space : Hard drop</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;