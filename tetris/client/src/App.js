import React, { useEffect, useState, useCallback, useRef } from 'react';
import BoardStage from './BoardStage';
import NewHomeScreen from './NewHomeScreen';
import ReadyScreen from './ReadyScreen';
import GameOverScreen from './GameOverScreen';
import ScorePanel from './ScorePanel';
import './App.css';

// Import server connection manager instead of direct socket.io
import serverManager from './utils/serverConnection';
import { saveGameSession, getGameSession, clearGameSession } from './utils/sessionStorage';

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
    return { client: { serverAddresses: ["http://localhost:3001"] } };
  }
};

// Add debug logger at the top of the file
const DEBUG = {
  events: true,
  state: true,
  render: true
};

function debugLog(type, message, data) {
  if (DEBUG[type]) {
    console.log(`[DEBUG:${type}] ${message}`, data !== undefined ? data : '');
  }
}

function App() {
  const [socketId, setSocketId] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [isGameOver, setIsGameOver] = useState(false);
  const [gameOverData, setGameOverData] = useState(null);
  const [isConnecting, setIsConnecting] = useState(true);
  const [error, setError] = useState(null);
  const [socketError, setSocketError] = useState(null);
  const [serverStatus, setServerStatus] = useState('connecting');
  const [connectedServer, setConnectedServer] = useState(null);

  // Hard‐drop guard so holding space won't repeat
  const hardDropActiveRef = useRef(false);

  // Add state for background rotation
  const [currentBackgroundIndex, setCurrentBackgroundIndex] = useState(0);
  const backgroundIntervalRef = useRef(null);

  // Add state for timer and scoring
  const [elapsedTime, setElapsedTime] = useState(0);
  const [currentScore, setCurrentScore] = useState(0);
  const [lastScoreChange, setLastScoreChange] = useState(0);
  const [level, setLevel] = useState(1);
  const timerIntervalRef = useRef(null);

  // Connect to servers on component mount
  useEffect(() => {
    const connectToServers = async () => {
      try {
        setIsConnecting(true);
        setServerStatus('connecting');
        
        // Initialize server manager
        await serverManager.initialize(
          // onConnected callback
          (activeSocket) => {
            debugLog('events', 'Connected to leader server with ID:', activeSocket.id);
            setSocketId(activeSocket.id);
            setIsConnecting(false);
            setServerStatus('connected');
            setSocketError(null);
            
            // Get the server URL and update the state
            const serverUrl = activeSocket.io.uri;
            const parsedUrl = new URL(serverUrl);
            setConnectedServer(`${parsedUrl.hostname}:${parsedUrl.port}`);
            
            // Explicitly request initial state after connection
            serverManager.emit('requestInitialState');
          },
          
          // onStateChange callback
          (change) => {
            if (change.type === 'connected') {
              try {
                // Parse the URL but preserve the hostname from config
                const configUrl = new URL(change.server);
                setConnectedServer(`${configUrl.hostname}:${configUrl.port}`);
              } catch (e) {
                setConnectedServer(change.server);
              }
            }
            else if (change.type === 'leaderChanged') {
              debugLog('events', 'Leader server changed to:', change.server.url);
              setSocketId(change.server.socket.id);
              
              // Update server URL info
              try {
                const serverUrl = change.server.url;
                const parsedUrl = new URL(serverUrl);
                setConnectedServer(`${parsedUrl.hostname}:${parsedUrl.port}`);
              } catch (e) {
                setConnectedServer(change.server.url || 'unknown');
              }
              
              // Server change notification
              setServerStatus('switchedServer');
              setTimeout(() => setServerStatus('connected'), 3000);
              
              // Re-request initial state after server change
              serverManager.emit('requestInitialState');
            }
            else if (change.type === 'disconnected') {
              setConnectedServer(null);
            }
            else if (change.type === 'allServersDown') {
              setSocketError('All servers are down. Please try again later.');
              setServerStatus('disconnected');
              setConnectedServer(null);
            }
          }
        );
        
        // Set up event handlers
        
        // Handle initial state
        serverManager.on('init', (initialState) => {
          debugLog('events', 'Received init event with state:', initialState);
          setGameState(initialState);
        });
        
        // Handle room rejoined - when reconnecting to existing session
        serverManager.on('roomRejoined', (data) => {
          debugLog('events', 'Received roomRejoined event with data:', data);
          
          // Save the new session data with updated socket ID
          saveGameSession({
            roomCode: data.roomCode,
            playerName: data.gameState.players[serverManager.getSocketId()]?.name || 'Player',
            socketId: serverManager.getSocketId()
          });
          
          // Track successful reconnection to avoid fallback attempts
          serverManager.hasRejoinedRoom = true;
          
          // Update game state for player
          setGameState(data.gameState);
          setError(null);
        });
        
        // Handle room creation - save session
        serverManager.on('roomCreated', (data) => {
          debugLog('events', 'Received roomCreated event with data:', data);
          
          // Save session data for automatic reconnection
          saveGameSession({
            roomCode: data.roomCode,
            playerName: data.gameState.players[serverManager.getSocketId()]?.name || 'Player',
            socketId: serverManager.getSocketId()
          });
          
          debugLog('state', 'Setting appPhase to readyscreen from:', gameState?.appPhase);
          setGameState(prevState => {
            const newState = {
              ...data.gameState,
              appPhase: 'readyscreen'
            };
            debugLog('state', 'New gameState after roomCreated:', newState);
            return newState;
          });
          setError(null);
        });
        
        // Handle room join - save session
        serverManager.on('roomJoined', (data) => {
          debugLog('events', 'Received roomJoined event with data:', data);
          
          // Save session data for automatic reconnection
          saveGameSession({
            roomCode: data.roomCode,
            playerName: data.gameState.players[serverManager.getSocketId()]?.name || 'Player',
            socketId: serverManager.getSocketId()
          });
          
          setGameState(prevState => {
            const newState = {
              ...data.gameState,
              appPhase: 'readyscreen'
            };
            debugLog('state', 'New gameState after roomJoined:', newState);
            return newState;
          });
          setError(null);
        });
        
        // Handle leaving room - clear session
        serverManager.on('roomLeft', (data) => {
          debugLog('events', 'Received roomLeft event with data:', data);
          
          // Clear session data when leaving room
          clearGameSession();
          
          // Set app phase to homescreen
          setGameState({
            appPhase: 'homescreen',
            players: {},
            roomCode: null,
            activePlayers: [],
            readyPlayers: []
          });
        });
        
        // Handle game state updates
        serverManager.on('gameState', (newState) => {
          // Improve debug logging to show what we receive
          debugLog('events', 'Received gameState update with appPhase:', newState?.appPhase);
          debugLog('events', 'Game state type:', typeof newState);

          // Log when we're receiving the init state
          if (gameState === null) {
            console.log('Game state received:', newState);
            console.log('Current app phase:', gameState?.appPhase);
            
            // If newState is valid, use it
            if (newState && typeof newState === 'object' && newState.appPhase) {
              debugLog('state', 'Setting initial game state with appPhase:', newState.appPhase);
              setGameState(newState);
            } else {
              // Create a default homescreen state if the received state is invalid
              console.warn('Received invalid game state, using default homescreen state');
              setGameState({
                appPhase: 'homescreen',
                socketId: serverManager.getSocketId(),
                players: {},
                activePlayers: [],
                readyPlayers: [],
                gameInProgress: false
              });
            }
          } else {
            setGameState(prevState => {
              // If we're showing a readyscreen from a room we just created or joined,
              // don't let a gameState event with homescreen override it
              if (prevState?.appPhase === 'readyscreen' && newState?.appPhase === 'homescreen') {
                debugLog('state', 'Ignoring homescreen gameState while in readyscreen');
                return prevState;
              }
              debugLog('state', 'Updating gameState from:', prevState?.appPhase, 'to:', newState?.appPhase);
              return newState;
            });
          }
        });

        // Handle errors
        serverManager.on('error', ({ message }) => {
          debugLog('events', 'Received server error:', message);
          setError(message);
        });
        
        // Handle game over - clear session
        serverManager.on('gameOver', (data) => {
          console.log('Game over with data:', data);
          
          // Clear session on game over
          clearGameSession();
          
          setIsGameOver(true);
          setGameOverData(data);
        });
        
        // Handle player joined notification
        serverManager.on('playerJoined', ({ playerId, player, gameState }) => {
          console.log(`Player joined: ${playerId}`);
          setGameState(gameState);
        });
        
        // Handle player left notification
        serverManager.on('playerLeft', ({ playerId, gameState }) => {
          console.log(`Player left: ${playerId}`);
          setGameState(gameState);
        });
        
        // Handle host assignment (when previous host leaves)
        serverManager.on('hostAssigned', ({ gameState }) => {
          console.log('You are now the host');
          setGameState(gameState);
        });
      } catch (err) {
        console.error('Error connecting to servers:', err);
        setSocketError(`Error connecting to servers: ${err.message}`);
        setIsConnecting(false);
        setServerStatus('error');
      }
    };
    
    connectToServers();
    
    // Cleanup on component unmount
    return () => {
      serverManager.disconnect();
    };
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
    const currentSocketId = serverManager.getSocketId();

    // Update current player score state for the score panel
    if (currentSocketId) {
      const currentPlayerEntry = playerEntries.find(([id]) => id === currentSocketId);
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
  }, [currentScore, level]);

  // Keyboard control handlers
  useEffect(() => {
    if (!socketId || !gameState) return;

    const handleKeyDown = (e) => {
      // Only process key events if game is in progress
      if (gameState.appPhase === 'playing') {
        switch (e.code) {
          case 'ArrowLeft':
            // First send immediate move, then start DAS
            serverManager.emit('playerAction', { type: 'moveLeft' });
            serverManager.emit('playerAction', { type: 'startDAS', direction: 'left' });
            break;
          case 'ArrowRight':
            // First send immediate move, then start DAS
            serverManager.emit('playerAction', { type: 'moveRight' });
            serverManager.emit('playerAction', { type: 'startDAS', direction: 'right' });
            break;
          case 'ArrowUp':
          case 'KeyZ':
            serverManager.emit('playerAction', { type: 'rotate' });
            break;
          case 'ArrowDown':
            serverManager.emit('playerAction', { type: 'softDrop' });
            break;
          case 'Space':
            // guard against auto‑repeat when holding space
            if (!hardDropActiveRef.current) {
              serverManager.emit('playerAction', { type: 'hardDrop' });
              hardDropActiveRef.current = true;
            }
            break;
          default:
            break;
        }
      } else if (gameState.appPhase === 'readyscreen') {
        // Handle ready toggle on X key press
        if (e.code === 'KeyX') {
          const isCurrentlyReady = gameState.readyPlayers && 
            gameState.readyPlayers.includes(socketId);
          console.log('X key pressed, toggling ready state:', !isCurrentlyReady);
          serverManager.emit('ready');
        }
      }
    };

    const handleKeyUp = (e) => {
      // Only process key events if game is in progress
      if (gameState.appPhase === 'playing') {
        switch (e.code) {
          case 'ArrowLeft':
          case 'ArrowRight':
            serverManager.emit('playerAction', { type: 'endDAS' });
            break;
          case 'ArrowDown':
            serverManager.emit('playerAction', { type: 'endSoftDrop' });
            break;
          case 'Space':
            // re‑enable hardDrop once key is released
            hardDropActiveRef.current = false;
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
  }, [socketId, gameState]);

  // Room management handlers
  const handleCreateRoom = useCallback((playerName) => {
    serverManager.emit('createRoom', playerName);
  }, []);
  
  const handleJoinRoom = useCallback((roomCode, playerName) => {
    serverManager.emit('joinRoom', { roomCode, playerName });
  }, []);
  
  const handleLeaveRoom = useCallback(() => {
    serverManager.emit('leaveRoom');
  }, []);

  // Handle player ready state
  const handlePlayerReady = useCallback((isReady) => {
    serverManager.emit('ready');  // Server expects no parameters
  }, []);

  // Handle game start
  const handleStartGame = useCallback(() => {
    serverManager.emit('startGame');
  }, []);

  // Handle game mode change
  const handleSetGameMode = useCallback((mode) => {
    serverManager.emit('setGameMode', mode);
  }, []);

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

  if (socketError) {
    return (
      <div className="App">
        <h1>Connection Error</h1>
        <p>{socketError}</p>
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
    console.log('No game state yet, showing loading screen');
    return <div className="App"><h1>Waiting for game state...</h1></div>;
  }
  console.log('Game state received:', gameState);
  console.log('Current app phase:', gameState.appPhase);

  // Render appropriate screen based on app phase
  return (
    <div
      className="App"
      style={{
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

  {/* Server Connection Indicator - Always visible */}
  <div 
    style={{
      position: 'fixed',
      top: '10px',
      right: '10px',
      background: 'rgba(0,0,0,0.7)',
      color: serverStatus === 'connected' ? '#00ff00' : 
            serverStatus === 'disconnected' ? '#ff0000' : 
            '#ffcc00',
      padding: '8px 12px',
      borderRadius: '4px',
      fontSize: '12px',
      zIndex: 1000,
      fontFamily: 'monospace',
      display: 'flex',
      flexDirection: 'column',
      backdropFilter: 'blur(3px)'
    }}
  >
    <span>Server: {connectedServer || 'None'}</span>
    <span style={{ 
      fontSize: '10px', 
      marginTop: '3px', 
      color: serverStatus === 'disconnected' ? '#ff6666' : '#aaa'
    }}>
      Status: {serverStatus}
      {serverStatus === 'disconnected' && ' - Reconnecting...'}
    </span>
  </div>

      {/* Server Status Notification */}
      {serverStatus === 'switchedServer' && (
        <div style={{
          position: 'fixed',
          top: '10px',
          left: '50%',
          transform: 'translateX(-50%)',
          backgroundColor: 'rgba(50, 50, 50, 0.9)',
          color: '#fff',
          padding: '10px 20px',
          borderRadius: '4px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.3)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          transition: 'opacity 0.3s ease',
          opacity: 1
        }}>
          <span style={{ marginRight: '10px' }}>⚠️</span>
          Reconnected to new server. Game continuing...
        </div>
      )}
      
      {gameState.appPhase === 'homescreen' && (
        <NewHomeScreen
          onCreateRoom={handleCreateRoom}
          onJoinRoom={handleJoinRoom}
          error={error}
        />
      )}
      
      {gameState.appPhase === 'readyscreen' && (
        <ReadyScreen
          roomCode={gameState.roomCode}
          players={gameState.players || {}}
          currentPlayerId={socketId}
          readyPlayers={gameState.readyPlayers || []}
          onReady={handlePlayerReady}
          onStartGame={handleStartGame}
          onLeaveRoom={handleLeaveRoom}
          onSetGameMode={handleSetGameMode}
          gameMode={gameState.gameMode}
          gameInProgress={gameState.gameInProgress}
          isHost={gameState.players?.[socketId]?.isHost}
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
              display: 'flex',
              alignItems: 'center',
              gap: '15px'
            }}>
              <div style={{
                fontSize: '14px',
                backgroundColor: '#444',
                padding: '5px 10px',
                borderRadius: '4px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center'
              }}>
                <span style={{fontSize: '10px', color: '#aaa'}}>ROOM</span>
                <span style={{fontWeight: 'bold'}}>{gameState.roomCode}</span>
              </div>
              <div style={{
                fontSize: '14px',
                backgroundColor: '#333',
                padding: '5px 10px',
                borderRadius: '4px'
              }}>
                Player: {socketId && socketId.substring(0, 4)}
              </div>
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
                    const isCurrentPlayer = id === socketId;
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
                              {player.name || `Player ${player.playerNumber || shortId}`}
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
          currentPlayerId={socketId}
          onTimeout={handleGameOverTimeout}
        />
      )}
    </div>
  );
}

export default App;