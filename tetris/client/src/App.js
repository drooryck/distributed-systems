import React, { useState, useEffect, useRef, useCallback } from 'react';
import io from 'socket.io-client';
import HomeScreen from './HomeScreen';
import GameOverScreen from './GameOverScreen';

// Load config file to get server address
const loadConfig = async () => {
  try {
    const response = await fetch('/config.json');
    if (!response.ok) {
      throw new Error(`Failed to load config: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn('Error loading config, using default server address:', error);
    return { client: { serverAddress: 'http://localhost:3001' } };
  }
};

// Map of tetromino values to colors
const COLORS = {
  1: 'cyan',    // I
  2: 'blue',    // J
  3: 'orange',  // L
  4: 'yellow',  // O
  5: 'green',   // S
  6: 'purple',  // T
  7: 'red'      // Z
};

// ----- GAME BOARD COMPONENT -----
const GameBoard = ({ board, players, currentPlayerId }) => {
  const canvasRef = useRef(null);
  const cellSize = 30; // each cell is 30px
  
  // Calculate canvas dimensions based on board size
  const canvasWidth = board?.[0]?.length ? board[0].length * cellSize : 300;
  const canvasHeight = board?.length ? board.length * cellSize : 600;

  useEffect(() => {
    if (!board || !Array.isArray(board) || board.length === 0 || !Array.isArray(board[0])) {
      console.warn("Invalid board structure:", board);
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw a dark background
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw the grid
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    
    // Draw grid lines
    for (let r = 0; r <= board.length; r++) {
      ctx.beginPath();
      ctx.moveTo(0, r * cellSize);
      ctx.lineTo(canvas.width, r * cellSize);
      ctx.stroke();
    }
    
    for (let c = 0; c <= board[0].length; c++) {
      ctx.beginPath();
      ctx.moveTo(c * cellSize, 0);
      ctx.lineTo(c * cellSize, canvas.height);
      ctx.stroke();
    }
    
    // Draw placed pieces on the board
    for (let r = 0; r < board.length; r++) {
      if (!Array.isArray(board[r])) {
        console.warn(`Invalid board row at index ${r}:`, board[r]);
        continue;
      }
      
      for (let c = 0; c < board[r].length; c++) {
        const cell = board[r][c];
        if (cell !== 0) {
          // If the cell has a complex structure (from server)
          if (typeof cell === 'object' && cell !== null) {
            const playerId = cell.playerId;
            if (!playerId) {
              ctx.fillStyle = 'gray';
            } else {
              const player = Object.values(players || {}).find(p => p && p.id === playerId.substring(0, 4));
              ctx.fillStyle = player ? player.color : 'gray';
            }
          } else {
            // If it's just a number (simple case)
            ctx.fillStyle = COLORS[cell] || 'gray';
          }
          
          ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize);
          ctx.strokeStyle = '#FFF';
          ctx.lineWidth = 1;
          ctx.strokeRect(c * cellSize, r * cellSize, cellSize, cellSize);
        }
      }
    }

    // Draw line clear animation if active
    if (Array.isArray(board.linesToClear) && board.linesToClear.length > 0) {
      board.linesToClear.forEach(rowIndex => {
        // Flash or highlight the rows being cleared
        const flash = Math.floor(Date.now() / 100) % 2 === 0;
        ctx.fillStyle = flash ? '#FFFFFF' : '#888888';
        ctx.fillRect(0, rowIndex * cellSize, canvas.width, cellSize);
      });
    }
      
    // Draw active tetromino for each player
    if (players && typeof players === 'object') {
      Object.values(players).forEach(player => {
        if (!player || !player.currentPiece || !player.currentPiece.shape) return;
        
        const { x, y, currentPiece, color } = player;
        const shape = currentPiece.shape;
        
        if (!Array.isArray(shape)) {
          console.warn("Invalid shape:", shape);
          return;
        }
        
        for (let r = 0; r < shape.length; r++) {
          if (!Array.isArray(shape[r])) {
            console.warn(`Invalid shape row at index ${r}:`, shape[r]);
            continue;
          }
          
          for (let c = 0; c < shape[r].length; c++) {
            if (shape[r][c] !== 0) {
              const boardX = x + c;
              const boardY = y + r;
              
              // Skip if out of bounds or above the board
              if (boardX < 0 || boardX >= board[0].length || 
                  boardY < 0 || boardY >= board.length) {
                continue;
              }
              
              ctx.fillStyle = color || currentPiece.color || 'gray';
              ctx.fillRect(boardX * cellSize, boardY * cellSize, cellSize, cellSize);
              ctx.strokeStyle = '#FFF';
              ctx.lineWidth = 1;
              ctx.strokeRect(boardX * cellSize, boardY * cellSize, cellSize, cellSize);
            }
          }
        }
      });
    }
    
  }, [board, players, currentPlayerId]);

  return (
    <div>
      <canvas
        ref={canvasRef}
        width={canvasWidth}
        height={canvasHeight}
        style={{ border: '2px solid #555' }}
      />
    </div>
  );
};

// ----- PLAYER LIST COMPONENT -----
const PlayerList = ({ players, currentPlayerId }) => {
  const currentPlayerShortId = currentPlayerId?.substring(0, 4);
  
  if (!players || typeof players !== 'object') {
    return <div>No players connected</div>;
  }
  
  return (
    <div style={{ marginBottom: '20px' }}>
      <h3 style={{ marginBottom: '10px' }}>Players</h3>
      
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column',
        gap: '10px',
        maxWidth: '250px'
      }}>
        {Object.values(players).map(player => {
          if (!player) return null;
          const isCurrentPlayer = player.id === currentPlayerShortId;
          
          return (
            <div 
              key={player.id}
              style={{ 
                display: 'flex',
                alignItems: 'center',
                padding: '8px',
                backgroundColor: '#333',
                borderRadius: '4px',
                borderLeft: `4px solid ${player.color}`,
              }}
            >
              <div 
                style={{ 
                  width: '15px', 
                  height: '15px', 
                  backgroundColor: player.color,
                  marginRight: '10px',
                  borderRadius: '3px'
                }}
              />
              
              <div style={{ flex: 1 }}>
                Player {player.playerNumber}
                {isCurrentPlayer && ' (You)'}
              </div>
              
              <div style={{ 
                marginLeft: 'auto', 
                fontWeight: 'bold', 
                fontSize: '14px',
                color: '#AAA'
              }}>
                {player.score}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ----- SCOREBOARD COMPONENT -----
const ScoreBoard = ({ players }) => {
  if (!players || typeof players !== 'object') {
    return null;
  }
  
  // Sort players by score in descending order
  const sortedPlayers = [...Object.values(players)].sort((a, b) => b.score - a.score);
  
  return (
    <div>
      <h3 style={{ marginBottom: '10px' }}>Scores</h3>
      
      <div style={{
        backgroundColor: '#222',
        padding: '10px',
        borderRadius: '4px',
        maxWidth: '250px'
      }}>
        {sortedPlayers.map(player => (
          <div 
            key={player.id}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '5px 0',
              borderBottom: '1px solid #444'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div 
                style={{ 
                  width: '10px', 
                  height: '10px', 
                  backgroundColor: player.color,
                  marginRight: '8px',
                  borderRadius: '2px'
                }}
              />
              <span>Player {player.playerNumber}</span>
            </div>
            <div style={{ fontWeight: 'bold' }}>{player.score}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ----- MAIN APP COMPONENT -----
function App() {
  const [socket, setSocket] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [isGameOver, setIsGameOver] = useState(false);
  const [gameOverData, setGameOverData] = useState(null);
  const [isConnecting, setIsConnecting] = useState(true);
  const [error, setError] = useState(null);
  
  // Connect to socket on component mount
  useEffect(() => {
    const connectToServer = async () => {
      try {
        setIsConnecting(true);
        
        // Load configuration
        const config = await loadConfig();
        const serverAddress = config.client?.serverAddress || 'http://localhost:3001';
        
        console.log(`Connecting to server at: ${serverAddress}`);
        
        // Create new socket connection
        const newSocket = io(serverAddress);
        setSocket(newSocket);
        
        // Socket event handlers
        newSocket.on('connect', () => {
          console.log('Connected to server');
          setIsConnecting(false);
        });
        
        newSocket.on('connect_error', (err) => {
          console.error('Connection error:', err);
          setError(`Connection error: ${err.message}`);
          setIsConnecting(false);
        });
        
        newSocket.on('init', (initialState) => {
          console.log('Received initial game state:', initialState);
          setGameState(initialState);
        });
        
        newSocket.on('gameState', (newState) => {
          setGameState(prevState => {
            // If we're showing gameInProgress screen, only update if returning to lobby
            if (prevState?.gameInProgress && !prevState.players[newSocket.id] && 
                newState.appPhase === 'playing') {
              // Don't update state - keep showing "Game in Progress" screen
              return prevState;
            }
            
            // Otherwise update normally
            return newState;
          });
        });
        
        newSocket.on('gameOver', (data) => {
          console.log('Game over with data:', data);
          setIsGameOver(true);
          setGameOverData(data);
        });
        
        // Return cleanup function
        return () => {
          console.log('Disconnecting socket');
          newSocket.disconnect();
        };
      } catch (err) {
        console.error('Error connecting to server:', err);
        setError(`Error connecting to server: ${err.message}`);
        setIsConnecting(false);
      }
    };
    
    connectToServer();
  }, []);
  
  // Keyboard control handlers
  useEffect(() => {
    if (!socket || !gameState) return;
    
    const handleKeyDown = (e) => {
      // Only process key events if game is in progress
      if (gameState.appPhase === 'playing') {
        switch (e.code) {
          case 'ArrowLeft':
            // First send immediate move, then start DAS
            socket.emit('playerAction', { type: 'moveLeft' });
            socket.emit('playerAction', { type: 'startDAS', direction: 'left' });
            break;
          case 'ArrowRight':
            // First send immediate move, then start DAS
            socket.emit('playerAction', { type: 'moveRight' });
            socket.emit('playerAction', { type: 'startDAS', direction: 'right' });
            break;
          case 'ArrowUp':
          case 'KeyZ':
            socket.emit('playerAction', { type: 'rotate' });
            break;
          case 'ArrowDown':
            socket.emit('playerAction', { type: 'softDrop' });
            break;
          case 'Space':
            socket.emit('playerAction', { type: 'hardDrop' });
            break;
          default:
            break;
        }
      }
    };

    const handleKeyUp = (e) => {
      // Only process key events if game is in progress
      if (gameState.appPhase === 'playing') {
        switch (e.code) {
          case 'ArrowLeft':
          case 'ArrowRight':
            socket.emit('playerAction', { type: 'endDAS' });
            break;
          case 'ArrowDown':
            socket.emit('playerAction', { type: 'endSoftDrop' });
            break;
          default:
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [socket, gameState]);

  // Handle player ready state
  const handlePlayerReady = useCallback((isReady) => {
    if (socket) {
      socket.emit('playerReady', isReady);
    }
  }, [socket]);

  // Handle game start
  const handleStartGame = useCallback(() => {
    if (socket) {
      socket.emit('startGame');
    }
  }, [socket]);

  // Handle game mode change
  const handleSetGameMode = useCallback((mode) => {
    if (socket) {
      socket.emit('setGameMode', mode);
    }
  }, [socket]);

  // Handle game over timeout
  const handleGameOverTimeout = useCallback(() => {
    setIsGameOver(false);
    setGameOverData(null);
  }, []);

  // Show loading or error screen
  if (isConnecting) {
    return <div className="App"><h1>Connecting to server...</h1></div>;
  }
  
  if (error) {
    return (
      <div className="App">
        <h1>Connection Error</h1>
        <p>{error}</p>
        <p>Please check that the server is running and the configuration is correct.</p>
        <button 
          onClick={() => window.location.reload()}
          style={{
            padding: '10px 20px',
            backgroundColor: '#FF5733',
            border: 'none',
            borderRadius: '4px',
            color: 'white',
            cursor: 'pointer',
            marginTop: '20px'
          }}
        >
          Retry Connection
        </button>
      </div>
    );
  }

  // Show loading screen if no game state
  if (!gameState) {
    return <div className="App"><h1>Waiting for game state...</h1></div>;
  }

  // Home screen or game screen based on app phase
  return (
    <div className="App">
      {gameState.appPhase === 'homescreen' && (
        <HomeScreen
          players={gameState.players || {}}
          currentPlayerId={socket?.id}
          readyPlayers={gameState.readyPlayers || []}
          onReady={handlePlayerReady}
          onStartGame={handleStartGame}
          onSetGameMode={handleSetGameMode}
          gameMode={gameState.gameMode}
          gameInProgress={gameState.gameInProgress}
          isRejoining={gameState.players?.[socket?.id]?.isRejoining}
        />
      )}
      
      {gameState.appPhase === 'playing' && (
        <>
          <h1>Tetristributed</h1>
          <p>Connected as player: {socket?.id && socket.id.substring(0, 4)}</p>
          <div style={{ display: 'flex', gap: '20px', marginBottom: '20px' }}>
            <GameBoard 
              board={gameState.board || []} 
              players={gameState.players || {}}
              currentPlayerId={socket?.id}
            />
            <div>
              <PlayerList players={gameState.players || {}} currentPlayerId={socket?.id} />
              <ScoreBoard players={gameState.players || {}} />
            </div>
          </div>
        </>
      )}
      
      {isGameOver && gameOverData && (
        <GameOverScreen 
          gameOverData={gameOverData} 
          onTimeout={handleGameOverTimeout} 
        />
      )}
    </div>
  );
}

export default App;