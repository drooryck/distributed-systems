import React, { useEffect, useState, useCallback, useRef } from 'react';
import { io } from 'socket.io-client';
import { connectToCluster } from './serverDiscovery';
import BoardStage from './BoardStage';
import NewHomeScreen from './NewHomeScreen';
import ReadyScreen from './ReadyScreen';
import GameOverScreen from './GameOverScreen';
import ScorePanel from './ScorePanel';
import './App.css';

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
    return { serverAddress: 'http://localhost:3001' };
  }
};

// Debug logging
const DEBUG = {
  events: true,
  state: true,
  render: false
};

function debugLog(type, ...args) {
  if (DEBUG[type]) {
    console.log(`[DEBUG:${type}]`, ...args);
  }
}

// Function to get current background URL
const getBackgroundUrl = (index) => {
  return `${process.env.PUBLIC_URL}/backgrounds/${BACKGROUND_IMAGES[index]}`;
};

// App component
function App() {
  const [socket, setSocket] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [isGameOver, setIsGameOver] = useState(false);
  const [gameOverData, setGameOverData] = useState(null);
  const [isConnecting, setIsConnecting] = useState(true);
  const [error, setError] = useState(null);
  const [socketError, setSocketError] = useState(null);

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

  // For reconnection logic
  const reconnectTimeoutRef = useRef(null);
  const reconnectionAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;
  const lastGameStateRef = useRef(null);

  // Function to get current background URL
  const getCurrentBackgroundUrl = () => {
    return getBackgroundUrl(currentBackgroundIndex);
  };

  // Connect to socket on component mount
  useEffect(() => {
    const connectToServer = async () => {
      try {
        setIsConnecting(true);
        setSocketError(null);

        const currentUrl = window.location.origin;

        // Try to connect to the cluster
        let newSocket;
        try {
          debugLog('events', 'Attempting to connect to server cluster');
          newSocket = await connectToCluster(currentUrl);
        } catch (clusterError) {
          debugLog('events', 'Cluster connection failed, falling back to direct connection', clusterError);
          
          // Fall back to direct connection
          const config = await loadConfig();
          const serverAddress = config.client?.serverAddress || config.serverAddress || 'http://localhost:3001';
          
          debugLog('events', 'Connecting to server:', serverAddress);
          newSocket = io(serverAddress);
        }
        
        setSocket(newSocket);

        // Socket event handlers
        newSocket.on('connect', () => {
          debugLog('events', 'Socket connected with ID:', newSocket.id);
          setIsConnecting(false);
          setSocketError(null);
          reconnectionAttemptsRef.current = 0;
        });

        newSocket.on('connect_error', (err) => {
          debugLog('events', 'Connection error:', err.message);
          setSocketError(`Connection error: ${err.message}`);
          setIsConnecting(false);
        });

        // Handle leader information updates
        newSocket.on('leaderInfo', (info) => {
          debugLog('events', 'Leader info received:', info);
          
          if (!info.isLeader && info.leaderAddress) {
            debugLog('events', 'Redirecting to leader at:', info.leaderAddress);
            
            // Disconnect from current socket
            newSocket.disconnect();
            
            // Connect to the leader
            const leaderSocket = io(info.leaderAddress);
            
            // Set up all event handlers on the new socket
            leaderSocket.on('connect', () => {
              debugLog('events', 'Connected to leader with ID:', leaderSocket.id);
              setIsConnecting(false);
              setSocketError(null);
              reconnectionAttemptsRef.current = 0;
            });
        
            leaderSocket.on('gameState', (newGameState) => {
              debugLog('state', 'Received gameState from leader:', newGameState);
              setGameState(newGameState);
              
              // Update score if available
              if (newGameState && newGameState.appPhase === 'playing') {
                const player = newGameState.players[leaderSocket.id];
                if (player) {
                  const newScore = player.score || 0;
                  if (newScore !== currentScore) {
                    setLastScoreChange(Date.now());
                    setCurrentScore(newScore);
                  }
                }
              }
            });
        
            leaderSocket.on('disconnect', (reason) => {
              debugLog('events', 'Disconnected from leader:', reason);
              // Add reconnection logic here if needed
            });
        
            // Add other necessary event handlers
            leaderSocket.on('init', (initialState) => {
              debugLog('events', 'Received init from leader:', initialState);

              // re-initialize your homescreen state
              setGameState({
                appPhase: initialState.appPhase,
                players: {},
                roomCode: null,
                activePlayers: [],
                readyPlayers: []
              });
              
            });
            
            leaderSocket.on('error', (err) => {
              debugLog('events', 'Leader socket error:', err);
              setError(err.message);
            });
        
            // Set the socket state to the new leader socket
            setSocket(leaderSocket);
          }
        });

        // Handle initial state
        newSocket.on('init', (initialState) => {
          debugLog('events', 'Received init event with state:', initialState);
          // Apply initial state as gameState so UI can render homescreen
          setGameState({
            appPhase: initialState.appPhase,
            players: {},
            roomCode: null,
            activePlayers: [],
            readyPlayers: []
          });
        });

        // Handle game state updates
        newSocket.on('gameState', (newGameState) => {
          debugLog('state', 'Received gameState update:', newGameState);
          
          setGameState((prevState) => {
            // Store the game state for potential reconnection
            if (newGameState) {
              lastGameStateRef.current = newGameState;
            }
            
            // Special case to prevent accidentally going back to homescreen
            if (prevState?.appPhase === 'readyscreen' && newGameState?.appPhase === 'homescreen') {
              debugLog('state', 'Ignoring homescreen gameState while in readyscreen');
              return prevState;
            }
            
            return newGameState;
          });
          
          // Update score if available
          if (newGameState && newGameState.appPhase === 'playing') {
            // Find the player that corresponds to this client
            const player = newGameState.players[newSocket.id];
            if (player) {
              const newScore = player.score || 0;
              if (newScore !== currentScore) {
                setLastScoreChange(Date.now());
                setCurrentScore(newScore);
              }
            }
          }
        });

        // Handle room creation
        newSocket.on('roomCreated', ({ roomCode, gameState }) => {
          debugLog('events', `Room created: ${roomCode}`);
          setGameState(gameState);
        });

        // Handle joining a room
        newSocket.on('roomJoined', ({ roomCode, gameState }) => {
          debugLog('events', `Joined room: ${roomCode}`);
          setGameState(gameState);
        });

        // Handle player joining
        newSocket.on('playerJoined', ({ playerId, gameState }) => {
          debugLog('events', `Player joined: ${playerId}`);
          setGameState(gameState);
        });

        // Handle player leaving
        newSocket.on('playerLeft', ({ playerId, gameState }) => {
          debugLog('events', `Player left: ${playerId}`);
          setGameState(gameState);
        });
        
        // Handle host assignment (when previous host leaves)
        newSocket.on('hostAssigned', ({ gameState }) => {
          debugLog('events', 'You are now the host');
          setGameState(gameState);
        });

        // Handle game over
        newSocket.on('gameOver', (data) => {
          debugLog('events', 'Game over:', data);
          setIsGameOver(true);
          setGameOverData(data);
        });

        // Handle server errors
        newSocket.on('error', (err) => {
          debugLog('events', 'Server error:', err);
          setError(err.message);
        });

        // Handle disconnection with reconnection logic
        newSocket.on('disconnect', (reason) => {
          debugLog('events', 'Socket disconnected:', reason);
          
          // If the disconnect was not initiated by the client, attempt to reconnect
          if (reason === 'io server disconnect' || reason === 'transport close' || reason === 'transport error') {
            if (reconnectionAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
              debugLog('events', `Attempting to reconnect (${reconnectionAttemptsRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})...`);
              setIsConnecting(true);
              
              // Clear any existing reconnection timeout
              if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
              }
              
              // Exponential backoff for reconnection
              const delay = Math.min(1000 * Math.pow(2, reconnectionAttemptsRef.current), 10000);
              reconnectTimeoutRef.current = setTimeout(async () => {
                reconnectionAttemptsRef.current++;
                connectToServer();
              }, delay);
            } else {
              debugLog('events', 'Max reconnection attempts reached');
              setSocketError('Could not reconnect to the server. Please refresh the page.');
              setIsConnecting(false);
            }
          }
        });

        // Return cleanup function
        return () => {
          debugLog('events', 'Cleaning up socket connection');
          
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
          }
          
          newSocket.disconnect();
        };
      } catch (err) {
        console.error('Error connecting to server:', err);
        setSocketError(`Error connecting to server: ${err.message}`);
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
      backgroundIntervalRef.current = setInterval(() => {
        setCurrentBackgroundIndex((prevIndex) => 
          (prevIndex + 1) % BACKGROUND_IMAGES.length
        );
      }, BACKGROUND_CHANGE_INTERVAL);
    }

    return () => {
      if (backgroundIntervalRef.current) {
        clearInterval(backgroundIntervalRef.current);
      }
    };
  }, [gameState?.appPhase]);

  // Timer effect for gameplay
  useEffect(() => {
    if (gameState && gameState.appPhase === 'playing') {
      if (!timerIntervalRef.current) {
        const startTime = Date.now();
        timerIntervalRef.current = setInterval(() => {
          const elapsed = Math.floor((Date.now() - startTime) / 1000);
          setElapsedTime(elapsed);
          
          // Update level based on time (every 30 seconds)
          const newLevel = Math.max(1, Math.floor(elapsed / 30) + 1);
          if (newLevel !== level) {
            setLevel(newLevel);
          }
        }, 1000);
      }
    } else {
      // Clear timer when not playing
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
      
      // Reset timer and level when game ends
      if (gameState && gameState.appPhase !== 'playing') {
        setElapsedTime(0);
        setLevel(1);
      }
    }
    
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, [gameState?.appPhase, level]);

  // Handle keydown events for gameplay
  const handleKeyDown = useCallback((e) => {
    if (!socket || !gameState || gameState.appPhase !== 'playing') return;

    // Prevent default behavior for game controls
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Space', 'KeyZ'].includes(e.code)) {
      e.preventDefault();
    }

    // Only handle keys that aren't being repeated (except down)
    if (!e.repeat || e.code === 'ArrowDown') {
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
          // guard against auto‑repeat when holding space
          if (!hardDropActiveRef.current) {
            socket.emit('playerAction', { type: 'hardDrop' });
            hardDropActiveRef.current = true;
          }
          break;
        default:
          break;
      }
    }
  }, [socket, gameState]);

  // Handle keyup events to stop DAS (delayed auto-shift)
  const handleKeyUp = useCallback((e) => {
    if (!socket || !gameState || gameState.appPhase !== 'playing') return;
    
    switch (e.code) {
      case 'ArrowLeft':
      case 'ArrowRight':
        socket.emit('playerAction', { type: 'stopDAS' });
        break;
      case 'Space':
        hardDropActiveRef.current = false;
        break;
      default:
        break;
    }
  }, [socket, gameState]);

  // Add key event listeners
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [handleKeyDown, handleKeyUp]);

  // Ensure room events are handled on each socket reconnect
  useEffect(() => {
    if (!socket) return;

    socket.on('roomCreated', ({ roomCode, gameState }) => {
      debugLog('events', `Room created: ${roomCode}`);
      setGameState(gameState);
    });

    socket.on('roomJoined', ({ roomCode, gameState }) => {
      debugLog('events', `Joined room: ${roomCode}`);
      setGameState(gameState);
    });

    return () => {
      socket.off('roomCreated');
      socket.off('roomJoined');
    };
  }, [socket]);

  // Create a room
  const createRoom = useCallback((playerName) => {
    if (socket) {
      debugLog('events', 'Creating room with player name:', playerName);
      socket.emit('createRoom', playerName);
    }
  }, [socket]);

  // Join a room
  const joinRoom = useCallback((roomCode, playerName) => {
    if (socket) {
      debugLog('events', `Joining room ${roomCode} with player name: ${playerName}`);
      socket.emit('joinRoom', { roomCode, playerName });
    }
  }, [socket]);

  // Leave a room
  const leaveRoom = useCallback(() => {
    if (socket) {
      debugLog('events', 'Leaving room');
      socket.emit('leaveRoom');
    }
  }, [socket]);

  // Set player ready state
  const setReady = useCallback((isReady) => {
    if (socket) {
      debugLog('events', `Setting ready state: ${isReady}`);
      socket.emit('playerReady', isReady);
    }
  }, [socket]);

  // Start the game (host only)
  const startGame = useCallback(() => {
    if (socket) {
      debugLog('events', 'Starting game');
      socket.emit('startGame');
    }
  }, [socket]);

  // Show error message if there's a socket error
  if (socketError) {
    return (
      <div className="App error-screen">
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
    return <div className="App"><h1>Waiting for game state...</h1></div>;
  }

  // Render appropriate screen based on app phase
  return (
    <div
      className="App"
      style={{
        ...(gameState.appPhase === 'playing' && {
          backgroundImage: `url(${getCurrentBackgroundUrl()})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }),
      }}
    >
      {gameState.appPhase === 'homescreen' && (
        <NewHomeScreen
          onCreateRoom={createRoom}
          onJoinRoom={joinRoom}
        />
      )}
      
      {gameState.appPhase === 'readyscreen' && (
        <ReadyScreen
          gameState={gameState}
          socketId={socket ? socket.id : null}
          onReady={setReady}
          onLeaveRoom={leaveRoom}
          onStartGame={startGame}
        />
      )}
      
      {gameState.appPhase === 'playing' && (
        <>
          <BoardStage
            board={gameState.board}
            players={gameState.players}
            socketId={socket ? socket.id : null}
          />
          <ScorePanel
            score={currentScore}
            lastScoreChange={lastScoreChange}
            level={level}
            time={elapsedTime}
          />
        </>
      )}
      
      {gameState.appPhase === 'gameover' && (
        <GameOverScreen
          gameOverData={gameOverData}
          onPlayAgain={() => {
            setIsGameOver(false);
            leaveRoom();
          }}
        />
      )}
    </div>
  );
}

export default App;