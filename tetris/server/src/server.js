const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const {
  createGameState, handleNewPlayer, handleDisconnect, handlePlayerAction, isValidMove,
  isValidMoveOnBoard, getRandomTetromino, placeTetromino, clearLines, createEmptyBoard, getBoardDimensions
} = require('./gameState');

const fs = require('fs');
const path = require('path');

// Load configuration file
let config;
try {
  const configPath = path.resolve(__dirname, '..', 'config.json');
  const configData = fs.readFileSync(configPath, 'utf8');
  config = JSON.parse(configData);
  console.log('Server configuration loaded');
} catch (error) {
  console.warn('Error loading server config.json, using defaults:', error.message);
  config = {
    ip: '0.0.0.0',
    port: 3001,
    cors: {
      origin: "*"
    }
  };
}


// Constants for game mechanics
const FRAME_RATE = 60, FRAME_DELAY = 1000 / FRAME_RATE;
const LOCK_DELAY = 30, DAS_DELAY = 12, DAS_REPEAT = 2, LINE_CLEAR_DELAY = 30, ENTRY_DELAY = 15;

// Create our initial game state (empty board, no players)
let gameState = createGameState();
let gameLoop;

// Improved piece locking function
function handlePieceLocking(gameState, playerId) {
  const player = gameState.players[playerId];
  if (!player || !player.currentPiece) return gameState;
  
  // Place the current piece on the board
  gameState.board = placeTetromino(gameState.board, player.currentPiece, player.x, player.y, playerId);
  
  // Clear lines and update score
  const { newBoard, linesCleared } = clearLines(gameState);
  gameState.board = newBoard;
  player.score += linesCleared * 100;
  
  // Start entry delay for new piece
  player.isWaitingForNextPiece = true;
  player.entryDelayTimer = 0;
  
  // Collect affected players first to avoid recursive calls
  const playersToLock = [];
  
  // Only check active players for collisions
  Array.from(gameState.activePlayers).forEach(otherPlayerId => {
    if (otherPlayerId !== playerId) {
      const otherPlayer = gameState.players[otherPlayerId];
      if (!otherPlayer || !otherPlayer.currentPiece || otherPlayer.isWaitingForNextPiece) return;
      
      try {
        if (!isValidMove(gameState.board, otherPlayer.currentPiece, otherPlayer.x, otherPlayer.y, otherPlayerId, gameState.players)) {
          console.log(`Collision detected for player ${otherPlayerId} after piece lock`);
          playersToLock.push(otherPlayerId);
        }
      } catch (error) {
        console.error(`Error checking collision for player ${otherPlayerId}:`, error);
      }
    }
  });
  
  // Lock the affected pieces in sequence
  playersToLock.forEach(idToLock => {
    const playerToLock = gameState.players[idToLock];
    if (!playerToLock || !playerToLock.currentPiece) return;
    
    gameState.board = placeTetromino(gameState.board, playerToLock.currentPiece, playerToLock.x, playerToLock.y, idToLock);
    playerToLock.isWaitingForNextPiece = true;
    playerToLock.entryDelayTimer = 0;
    console.log(`Forced lock for player ${idToLock}`);
  });
  
  // Handle lines cleared during force locking
  if (playersToLock.length > 0) {
    const { newBoard: updatedBoard, linesCleared: additionalLines } = clearLines(gameState);
    gameState.board = updatedBoard;
    
    if (additionalLines > 0) {
      player.score += additionalLines * 100;
      console.log(`Player ${playerId} got ${additionalLines} additional lines from chain reaction`);
    }
  }
  
  return gameState;
}

function updateGameState() {
  // Handle line clear animations
  if (gameState.lineClearActive) {
    gameState.lineClearTimer++;
    
    if (gameState.lineClearTimer >= LINE_CLEAR_DELAY) {
      // Animation finished, actually clear the lines
      const newBoard = [...gameState.board];
      gameState.linesToClear.forEach(rowIndex => {
        newBoard.splice(rowIndex, 1);
        newBoard.unshift(new Array(gameState.board[0].length).fill(0));
      });
      
      gameState.board = newBoard;
      gameState.lineClearActive = false;
      gameState.linesToClear = [];
    }
    return; // Skip other game updates during line clear
  }

  // Helper function to check if a piece is touching the ground or locked pieces
  function isTouchingGround(board, piece, x, y) {
    if (!piece || !piece.shape) return false;
    
    for (let r = 0; r < piece.shape.length; r++) {
      for (let c = 0; c < piece.shape[r].length; c++) {
        if (piece.shape[r][c]) {
          const boardY = y + r + 1, boardX = x + c;
          
          // Check if touching bottom or another piece
          if (boardY >= board.length) return true;
          if (board[boardY] && board[boardY][boardX] !== 0) return true;
        }
      }
    }
    return false;
  }

  // Process each player
  Object.keys(gameState.players).forEach(playerId => {
    const player = gameState.players[playerId];
    if (!player || !player.currentPiece) return;
    
    // Handle entry delay for new pieces
    if (player.isWaitingForNextPiece) {
      player.entryDelayTimer++;
      
      if (player.entryDelayTimer >= ENTRY_DELAY) {
        // Spawn new piece after delay
        player.currentPiece = getRandomTetromino();
        
        // Use player's specific spawn position instead of hardcoded position
        const playerIndex = Array.from(gameState.activePlayers).indexOf(playerId);
        const spawnPos = getSpawnPosition(playerIndex, gameState.board[0].length, gameState.activePlayers.size);
        player.x = spawnPos.x;
        player.y = spawnPos.y;
        
        player.isWaitingForNextPiece = false;
        
        // Check for game over condition
        if (!isValidMoveOnBoard(gameState.board, player.currentPiece, player.x, player.y, playerId)) {
          if (gameState.appPhase === 'playing') {
            console.log(`Game over for player ${playerId}`);
            gameState.appPhase = 'gameover';
            
            io.emit('gameOver', { playerId, score: player.score });
          
          // Reset game after timeout
          setTimeout(() => {
            // First, save player ready states before resetting
            const playerReadyStates = {};
            Object.keys(gameState.players).forEach(id => {
              // Track if they had pressed ready before the game
              playerReadyStates[id] = gameState.readyPlayers.includes(id);
            });
            
            clearInterval(gameLoop);
            
            // Save connected players before resetting
            const connectedPlayerIds = Object.keys(gameState.players);
            const playerData = {};
            
            // Save essential data for each player
            connectedPlayerIds.forEach(id => {
              playerData[id] = {
                id: gameState.players[id].id,
                playerNumber: gameState.players[id].playerNumber,
                color: gameState.players[id].color
              };
            });
            
            // Create fresh game state
            const newGameState = createGameState();
            
            // Track all socket IDs currently connected to the server
            const connectedSockets = Array.from(io.sockets.sockets.keys());
            
            // Re-add all connected players 
            connectedSockets.forEach(socketId => {
              if (playerData[socketId]) {
                newGameState.players[socketId] = {
                  id: playerData[socketId].id,
                  playerNumber: playerData[socketId].playerNumber,
                  color: playerData[socketId].color,
                  isReady: false, // Always start not ready
                  score: 0
                };
              } else {
                handleNewPlayer(newGameState, socketId);
              }
            });
            
            // Wait a short delay before sending the new state
            // This ensures clients have finished processing the game over
            setTimeout(() => {
              // Update gameState with our new state
              gameState = newGameState;
              gameState.appPhase = 'homescreen';
              gameState.gameInProgress = false;
              
              // Send updated game state to all players
              io.emit('gameState', gameState);
              gameLoop = setInterval(() => { io.emit('gameState', gameState); }, FRAME_DELAY);
            }, 500); // Small delay to avoid race conditions
          }, 5000);
        }
          
        return;
        }
      }
      return; // Skip regular fall logic while waiting
    } 
    
    // Handle DAS (Delayed Auto Shift)
    if (player.dasDirection) {
      player.dasTimer++;
      
      if (player.dasTimer >= DAS_DELAY) {
        player.dasRepeatTimer++;
        
        if (player.dasRepeatTimer >= DAS_REPEAT) {
          const moveOffset = player.dasDirection === 'left' ? -1 : 1;
          if (isValidMove(gameState.board, player.currentPiece, player.x + moveOffset, player.y, playerId, gameState.players)) {
            player.x += moveOffset;
          }
          player.dasRepeatTimer = 0;
        }
      }
    }
    
    // Regular falling logic
    player.fallTimer = (player.fallTimer || 0) + 1;
    
    const isTouchingFloorOrLockedPiece = isTouchingGround(gameState.board, player.currentPiece, player.x, player.y);
    const canFallWithoutCollision = isValidMove(gameState.board, player.currentPiece, player.x, player.y + 1, playerId, gameState.players);
    
    if (!isTouchingFloorOrLockedPiece && canFallWithoutCollision) {
      // Piece can still fall
      if (player.fallTimer >= player.fallSpeed) {
        player.y += 1;
        player.fallTimer = 0;
        player.isLocking = false;
        player.lockTimer = 0;
      }
    } else if (isTouchingFloorOrLockedPiece) {
      // Start locking only if touching ground or locked pieces
      if (!player.isLocking) {
        player.isLocking = true;
        player.lockTimer = 0;
      }
      
      player.lockTimer++;
      
      if (player.lockTimer >= LOCK_DELAY) {
        handlePieceLocking(gameState, playerId);
        player.isLocking = false;
      }
    } else {
      // Piece can't fall but not touching ground - just wait
      player.fallTimer = 0;
    }
  });
}

// Create Express app and HTTP server
const app = express();
const server = http.createServer(app);
const io = new Server(server, { 
  cors: { 
    origin: config.cors.origin,
    methods: ["GET", "POST"] 
  } 
});

app.get('/test', (req, res) => { res.send('Server is running!'); });

// Calculate spawn positions based on player number and board width
function getSpawnPosition(playerIndex, boardWidth, playerCount) {
  // For single player, use the standard Tetris position (middle-ish, at column 3)
  if (playerCount === 1) {
    return { x: 3, y: 0 }; // Standard Tetris spawn position
  }
  
  // For multiplayer games, distribute evenly across the board
  switch (playerCount) {
    case 2:
      // Two players: 1/3 and 2/3 in
      if (playerIndex === 0) return { x: Math.floor(boardWidth / 3) - 1, y: 0 };
      if (playerIndex === 1) return { x: Math.floor(boardWidth * 2 / 3) - 1, y: 0 };
      break;
      
    case 3:
      // Three players: 1/4, 2/4, 3/4 in
      if (playerIndex === 0) return { x: Math.floor(boardWidth / 4)-1, y: 0 };
      if (playerIndex === 1) return { x: Math.floor(boardWidth * 2 / 4)-1, y: 0 };
      if (playerIndex === 2) return { x: Math.floor(boardWidth * 3 / 4)-1, y: 0 };
      break;
      
    case 4:
      // Four players: 1/5, 2/5, 3/5, 4/5 in
      if (playerIndex === 0) return { x: Math.floor(boardWidth / 5)-1, y: 0 };
      if (playerIndex === 1) return { x: Math.floor(boardWidth * 2 / 5)-1, y: 0 };
      if (playerIndex === 2) return { x: Math.floor(boardWidth * 3 / 5)-1, y: 0 };
      if (playerIndex === 3) return { x: Math.floor(boardWidth * 4 / 5)-1, y: 0 };
      break;
      
    default:
      // Fallback: evenly distribute across the board
      const segment = 1 / (playerCount + 1);
      return { 
        x: Math.floor(boardWidth * segment * (playerIndex + 1)), 
        y: 0 
      };
  }
  
  // Fallback if not handled by cases above
  return { x: Math.floor(boardWidth / 2) - 1, y: 0 };
}

io.on('connection', (socket) => {
  console.log(`Client connected: ${socket.id}`);

  // If game in progress, show "game in progress" screen but don't add them to game
  if (gameState.appPhase === 'playing') {
    // Send limited game state that shows "Game in Progress" message
    const limitedState = {
      appPhase: 'homescreen',
      gameInProgress: true,
      players: {},  // Empty players object
      readyPlayers: [],
      gameMode: gameState.gameMode
    };
    socket.emit('init', limitedState);
    return;  // Don't add them to the active game
  }

  // Only add new players if no game is in progress
  gameState = handleNewPlayer(gameState, socket.id);
  socket.emit('init', gameState);
  io.emit('gameState', gameState);

  // Handle player ready state
  socket.on('playerReady', (isReady) => {
    const player = gameState.players[socket.id];
    if (!player) return;
    
    player.isReady = isReady;
    
    if (isReady) {
      if (!gameState.readyPlayers.includes(socket.id)) {
        gameState.readyPlayers.push(socket.id);
      }
    } else {
      gameState.readyPlayers = gameState.readyPlayers.filter(id => id !== socket.id);
    }
    
    io.emit('gameState', gameState);
  });
  
  // Handle game mode changes
  socket.on('setGameMode', (mode) => {
    const player = gameState.players[socket.id];
    if (player && player.playerNumber === 1) {
      gameState.gameMode = mode;
      io.emit('gameState', gameState);
    }
  });


  // Handle game start
// Replace lines 333-334 with this:

// Handle game start
// Replace the problematic section in the startGame handler:

// Replace the problematic section in the startGame handler:

// Update the startGame handler:

socket.on('startGame', () => {
  const player = gameState.players[socket.id];
  if (player && player.playerNumber === 1) {
    console.log('Game started by player 1');
    gameState.appPhase = 'playing';
    gameState.gameInProgress = true;
    
    // Only use ready players for the game
    const readyPlayers = Object.keys(gameState.players).filter(id => 
      gameState.readyPlayers.includes(id));
    
    // Get the count of ONLY READY players - this is crucial
    const readyPlayerCount = readyPlayers.length;
    console.log(`Starting game with ${readyPlayerCount} ready players`);
    
    // Get board dimensions based on READY players only
    const { rows, cols } = getBoardDimensions(readyPlayerCount);
    gameState.board = createEmptyBoard(rows, cols);
    
    // Update activePlayers set with only ready players
    gameState.activePlayers = new Set(readyPlayers);
    
    // Create a filtered game state that only includes ready players
    // This is what we'll send to players in the game
    const gameStateForActivePlayers = {
      ...gameState,
      players: {}
    };
    
    // Copy only ready players to the filtered state
    readyPlayers.forEach(id => {
      gameStateForActivePlayers.players[id] = {...gameState.players[id]};
    });
    
    // Initialize only ready players for the game
    readyPlayers.forEach((id, index) => {
      // Important: Calculate spawn based on THIS player's index among READY players
      const spawnPos = getSpawnPosition(index, cols, readyPlayerCount);
      
      // Update both states
      gameState.players[id].score = 0;
      gameState.players[id].x = spawnPos.x;
      gameState.players[id].y = spawnPos.y;
      gameState.players[id].currentPiece = getRandomTetromino();
      gameState.players[id].isWaitingForNextPiece = false;
      gameState.players[id].isLocking = false;
      gameState.players[id].lockTimer = 0;
      gameState.players[id].fallTimer = gameState.players[id].fallSpeed - 1;
      gameState.players[id].fallSpeed = 45; 
      gameState.players[id].softDropSpeed = 5;
      gameState.players[id].isActive = true;
      
      // Same for filtered state
      gameStateForActivePlayers.players[id] = {...gameState.players[id]};
      
      console.log(`Player ${id} (index ${index}) spawning at position (${spawnPos.x}, ${spawnPos.y})`);
    });
    
    // Find non-ready players
    const nonReadyPlayers = Object.keys(gameState.players).filter(id => 
      !gameState.readyPlayers.includes(id));
    
    // Special limited state for non-ready players
    const limitedState = {
      appPhase: 'homescreen',
      gameInProgress: true,
      players: {}, 
      readyPlayers: [],
      gameMode: gameState.gameMode
    };
    
    // Send appropriate state to each player
    readyPlayers.forEach(id => {
      const socket = io.sockets.sockets.get(id);
      if (socket) {
        // Send the filtered game state with only active players
        socket.emit('gameState', gameStateForActivePlayers);
      }
    });
    
    nonReadyPlayers.forEach(id => {
      const socket = io.sockets.sockets.get(id);
      if (socket) {
        socket.emit('gameState', limitedState);
      }
    });
    
    // Set up game loop
    clearInterval(gameLoop);
    gameLoop = setInterval(() => {
      updateGameState();
      
      // Create a fresh filtered state for each update
      const updatedGameStateForActive = {
        ...gameState,
        players: {}
      };
      
      // Only include active players
      readyPlayers.forEach(id => {
        if (gameState.players[id]) {
          updatedGameStateForActive.players[id] = {...gameState.players[id]};
        }
      });
      
      // Send filtered state to active players
      readyPlayers.forEach(id => {
        const socket = io.sockets.sockets.get(id);
        if (socket) {
          socket.emit('gameState', updatedGameStateForActive);
        }
      });
    }, FRAME_DELAY);
  }
});

  // Handle player actions
  socket.on('playerAction', (action) => {
    if (gameState.appPhase === 'playing') {
      const player = gameState.players[socket.id];
      if (!player) return;
      
      gameState = handlePlayerAction(gameState, socket.id, action);
      io.emit('gameState', gameState);
    }
  });

  // Handle player disconnects
  socket.on('disconnect', () => {
    console.log(`Client disconnected: ${socket.id}`);
    gameState.readyPlayers = gameState.readyPlayers.filter(id => id !== socket.id);
    gameState = handleDisconnect(gameState, socket.id);
    io.emit('gameState', gameState);
  });
});

// Start the server
const PORT = process.env.PORT || config.port;
const IP = config.ip;
server.listen(PORT, IP, () => { 
  console.log(`Server is running on ${IP}:${PORT}`); 
  console.log(`Players can connect to this server using the machine's network IP`);
});