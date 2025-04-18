import React, { useEffect, useState, useCallback, useRef } from 'react';
import { io } from 'socket.io-client';
import BoardStage from './BoardStage';
import HomeScreen from './HomeScreen';
import GameOverScreen from './GameOverScreen';
import ScorePanel from './ScorePanel';

// Background image configuration
const BACKGROUND_IMAGES = [
  'deep-tetris-color.jpg',
  'tetris-1920-x-1080-background-hyihqau5t3lalo4e.png',
  'tetris-2560-x-1600-background-3bjbi7nyulqbller.jpg',
];
const BACKGROUND_CHANGE_INTERVAL = 30000; // 30 seconds

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

function App() {
  const [socket, setSocket] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [isGameOver, setIsGameOver] = useState(false);
  const [gameOverData, setGameOverData] = useState(null);
  const [isConnecting, setIsConnecting] = useState(true);
  const [error, setError] = useState(null);
  
  // Add state for background rotation
  const [currentBackgroundIndex, setCurrentBackgroundIndex] = useState(0);
  const backgroundIntervalRef = useRef(null);
  
  // Add state for timer and scoring
  const [elapsedTime, setElapsedTime] = useState(0);
  const [currentScore, setCurrentScore] = useState(0);
  const [lastScoreChange, setLastScoreChange] = useState(0);
  const [level, setLevel] = useState(1);
  const timerIntervalRef = useRef(null);
  
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
          updatePlayerList(initialState.players || {});
        });
        
        newSocket.on('gameState', (newState) => {
          setGameState(prevState => {
            // If we're showing gameInProgress screen, only update if returning to lobby
            if (prevState?.gameInProgress && !prevState.players[newSocket.id] && 
                newState.appPhase === 'playing') {
              // Don't update state - keep showing "Game in Progress" screen
              return prevState;
            }
            
            // Update player list if we have new state
            if (newState) {
              updatePlayerList(newState.players || {});
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
  
  // Background rotation effect - only active during gameplay
  useEffect(() => {
    // Clear any existing background rotation interval
    if (backgroundIntervalRef.current) {
      clearInterval(backgroundIntervalRef.current);
      backgroundIntervalRef.current = null;
    }
    
    // Start background rotation when game is playing
    if (gameState && gameState.appPhase === 'playing') {
      // Randomize starting background
      setCurrentBackgroundIndex(Math.floor(Math.random() * BACKGROUND_IMAGES.length));
      
      // Set interval to rotate backgrounds
      backgroundIntervalRef.current = setInterval(() => {
        setCurrentBackgroundIndex(prevIndex => 
          (prevIndex + 1) % BACKGROUND_IMAGES.length
        );
      }, BACKGROUND_CHANGE_INTERVAL);
    }
    
    // Cleanup on unmount or phase change
    return () => {
      if (backgroundIntervalRef.current) {
        clearInterval(backgroundIntervalRef.current);
        backgroundIntervalRef.current = null;
      }
    };
  }, [gameState?.appPhase]);
  
  // Timer management based on game phase
  useEffect(() => {
    // Clean up the previous interval if it exists
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    
    if (gameState && gameState.appPhase === 'playing') {
      // Reset the timer when game starts
      setElapsedTime(0);
      setCurrentScore(0);
      setLastScoreChange(0);
      setLevel(1);
      
      // Start a new timer that updates every 10ms for centisecond precision
      timerIntervalRef.current = setInterval(() => {
        setElapsedTime(prevTime => prevTime + 10);
      }, 10);
      
      console.log('Timer started');
    }
    
    // Cleanup on unmount or phase change
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    };
  }, [gameState?.appPhase]); 
  
  // Update the player list for display and track current player's score
  const updatePlayerList = useCallback((players) => {
    if (!players || typeof players !== 'object') return;
    
    // Map player data to what we need
    const playerEntries = Object.entries(players);
    
    // Update current player score state for the score panel
    if (socket) {
      const currentPlayerEntry = playerEntries.find(([id]) => id === socket.id);
      if (currentPlayerEntry) {
        const [, currentPlayer] = currentPlayerEntry;
        
        // Update score if changed
        if (currentPlayer.score !== currentScore) {
          const scoreChange = Math.max(0, currentPlayer.score - currentScore);
          if (scoreChange > 0) {
            setLastScoreChange(scoreChange);
            // Reset the score change highlight after 1 second
            setTimeout(() => setLastScoreChange(0), 1000);
          }
          setCurrentScore(currentPlayer.score);
        }
        
        // Update level if changed
        if (currentPlayer.level && currentPlayer.level !== level) {
          setLevel(currentPlayer.level);
        }
      }
    }
  }, [currentScore, level, socket]);
  
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
      } else if (gameState.appPhase === 'homescreen') {
        // Handle ready toggle on X key press
        if (e.code === 'KeyX') {
          const isCurrentlyReady = gameState.readyPlayers.includes(socket.id);
          console.log('X key pressed, toggling ready state:', !isCurrentlyReady);
          socket.emit('playerReady', !isCurrentlyReady);
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

  // Get the current background image URL
  const getCurrentBackgroundUrl = () => {
    if (!BACKGROUND_IMAGES.length) return null;
    return `${process.env.PUBLIC_URL}/backgrounds/${BACKGROUND_IMAGES[currentBackgroundIndex]}`;
  };

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
    <div 
      className="App"
      style={{ 
        // Apply background image only during gameplay
        ...(gameState.appPhase === 'playing' && {
          backgroundImage: `url(${getCurrentBackgroundUrl()})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          transition: 'background-image 1s ease-in-out',
          minHeight: '100vh'
        })
      }}
      tabIndex="0"
    >
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
        <div style={{
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          backdropFilter: 'blur(5px)',
          padding: '20px',
          borderRadius: '10px',
          margin: '10px auto',
          maxWidth: '900px'
        }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '15px' 
          }}>
            <h1 style={{ margin: 0, fontSize: '28px', color: '#fff' }}>Tetristributed</h1>
            <div style={{ 
              fontSize: '14px', 
              backgroundColor: '#333', 
              padding: '5px 10px', 
              borderRadius: '4px' 
            }}>
              Player: {socket?.id && socket.id.substring(0, 4)}
            </div>
          </div>
          
          <div style={{ display: 'flex', gap: '20px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <BoardStage 
                board={gameState.board || []} 
                players={gameState.players || {}}
                linesToClear={gameState.linesToClear || []}
              />
            </div>
            
            <div style={{ 
              display: 'flex',
              flexDirection: 'column',
              minWidth: '220px'
            }}>
              {/* Integrated Score Panel with Timer */}
              <ScorePanel 
                score={currentScore}
                level={level}
                lastScoreChange={lastScoreChange}
                elapsedTime={elapsedTime}
              />
              
              {/* Players List */}
              <div style={{ 
                backgroundColor: 'rgba(40, 40, 40, 0.9)',
                padding: '12px',
                borderRadius: '8px',
                marginTop: '15px'
              }}>
                <h2 style={{ margin: '0 0 10px 0', fontSize: '18px', color: '#ccc' }}>Players</h2>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {Object.entries(gameState.players || {}).map(([id, player]) => {
                    const isCurrentPlayer = id === socket?.id;
                    const shortId = id.substring(0, 4);
                    
                    return (
                      <li 
                        key={id} 
                        style={{ 
                          margin: '6px 0',
                          padding: '8px',
                          backgroundColor: isCurrentPlayer ? '#444' : '#333',
                          borderLeft: `4px solid ${player.color || '#ccc'}`,
                          borderRadius: '4px',
                          transition: 'background-color 0.3s'
                        }}
                      >
                        <div style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'space-between' 
                        }}>
                          <div>
                            <span style={{ 
                              fontWeight: isCurrentPlayer ? 'bold' : 'normal',
                              color: isCurrentPlayer ? '#fff' : '#ccc'
                            }}>
                              Player {player.playerNumber || shortId}
                            </span>
                            {isCurrentPlayer && <span style={{ 
                              fontSize: '12px', 
                              marginLeft: '5px', 
                              color: '#ffcc00'
                            }}>
                              (You)
                            </span>}
                          </div>
                          <div style={{ 
                            backgroundColor: '#222', 
                            padding: '2px 6px', 
                            borderRadius: '3px',
                            fontSize: '14px',
                            fontWeight: 'bold'
                          }}>
                            {player.score || 0}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
                
                <div style={{ 
                  marginTop: '15px', 
                  padding: '8px', 
                  backgroundColor: '#222', 
                  borderRadius: '4px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '12px', color: '#aaa' }}>GAME MODE</div>
                  <div style={{ fontSize: '16px', fontWeight: 'bold', marginTop: '4px' }}>
                    {gameState.gameMode || 'Classic'}
                  </div>
                </div>
              </div>
              
              {/* Controls Help */}
              <div style={{ 
                backgroundColor: 'rgba(40, 40, 40, 0.7)',
                padding: '12px',
                borderRadius: '8px',
                marginTop: '15px',
                fontSize: '12px',
                color: '#aaa'
              }}>
                <div style={{ marginBottom: '5px', fontWeight: 'bold', color: '#ccc' }}>Controls:</div>
                <div>← → : Move</div>
                <div>↓ : Soft Drop</div>
                <div>↑ / Z : Rotate</div>
                <div>Space : Hard Drop</div>
              </div>
            </div>
          </div>
        </div>
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