const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const cors = require('cors');
const path = require('path');

// Import game state functions
const { 
  createGameState, 
  handleNewPlayer, 
  handleDisconnect, 
  handlePlayerAction,
  TETROMINOES,
  getRandomTetromino,
  isValidMove,
  isValidMoveOnBoard,
  placeTetromino,
  clearLines,
  createEmptyBoard,
  getBoardDimensions
} = require('./gameState');

// Initialize Express app and HTTP server
const app = express();
app.use(cors());
const server = http.createServer(app);

// Serve static files from client build
app.use(express.static(path.join(__dirname, '../../client/build')));

// Initialize Socket.IO with CORS settings
const io = socketIO(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

// Game configuration
const FRAME_DELAY = 1000 / 60; // 60 FPS
const LOCK_DELAY = 30; // frames to wait before locking a piece
const ENTRY_DELAY = 12; // frames to wait before spawning a new piece
const DAS_DELAY = 14; // frames to wait before auto-repeat kicks in
const DAS_REPEAT = 2; // frames between auto-repeat moves

// Create initial game state
let gameState = createGameState();
let gameLoop = null;

// Get spawn position based on player index and board size
function getSpawnPosition(playerIndex, boardWidth, totalPlayers) {
  // For single player, spawn in the middle
  if (totalPlayers === 1) return { x: Math.floor(boardWidth / 2) - 2, y: 0 };
  
  // For multiple players, divide the board into equal sections
  const sectionWidth = Math.floor(boardWidth / totalPlayers);
  return {
    x: playerIndex * sectionWidth + Math.floor(sectionWidth / 2) - 2,
    y: 0
  };
}

// Check if a piece is touching the ground or a locked piece
function isTouchingGround(board, tetromino, x, y) {
  if (!tetromino || !tetromino.shape) return false;
  
  for (let r = 0; r < tetromino.shape.length; r++) {
    for (let c = 0; c < tetromino.shape[r].length; c++) {
      if (tetromino.shape[r][c] !== 0) {
        const boardY = y + r + 1;
        const boardX = x + c;
        
        // Check if we're at the bottom of the board
        if (boardY >= board.length) return true;
        
        // Check if there's a piece below us
        if (boardY >= 0 && boardX >= 0 && boardX < board[0].length) {
          if (board[boardY][boardX] !== 0) return true;
        }
      }
    }
  }
  return false;
}

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

// Main game update function
function updateGameState() {
  // Handle ongoing line clear animation
  if (gameState.lineClearActive) {
    gameState.lineClearTimer++;
    
    // After animation completes, clear the lines
    if (gameState.lineClearTimer >= 30) { // 30 frames = 0.5 seconds at 60fps
      const newBoard = [...gameState.board];
      
      // Remove cleared lines
      for (const row of gameState.linesToClear.sort((a, b) => b - a)) {
        newBoard.splice(row, 1);
        newBoard.unshift(new Array(newBoard[0].length).fill(0));
      }
      
      gameState.board = newBoard;
      gameState.lineClearActive = false;
      gameState.linesToClear = [];
    }
  }
  
  // Process each active player
  Array.from(gameState.activePlayers).forEach(playerId => {
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
        
        // Reset the hard drop flag when spawning a new piece
        player.justPerformedHardDrop = false;
        
        // Check for game over condition
        if (!isValidMoveOnBoard(gameState.board, player.currentPiece, player.x, player.y, playerId)) {
          if (gameState.appPhase === 'playing') {
            console.log(`Game over for player ${playerId}`);
            gameState.appPhase = 'gameover';
            
            // Send game over event
            io.emit('gameOver', { 
              playerId, 
              score: player.score,
              isCurrentPlayer: true
            });
          
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
              
              // Start a simple loop to keep sending updates
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

// Handle Socket.IO connections
io.on('connection', (socket) => {
  console.log(`Player connected: ${socket.id}`);
  
  // If game in progress, show "game in progress" screen but don't add them to game
  if (gameState.appPhase === 'playing') {
    console.log(`Player ${socket.id} connected during active game - showing waiting screen only`);
    
    // Send limited game state that shows "Game in Progress" message
    // This is intentionally minimal to ensure they only see homescreen
    const limitedState = {
      appPhase: 'homescreen',
      gameInProgress: true,
      players: {},  // Empty players object
      readyPlayers: [],
      gameMode: gameState.gameMode
    };
    
    // First initialize them with limited state
    socket.emit('init', limitedState);
    
    // Then add them as a player for when the game ends
    gameState = handleNewPlayer(gameState, socket.id);
    
    // But immediately send them the limited state again to override
    // any automatic updates they might receive
    socket.emit('gameState', limitedState);
    
    // Return without adding them to the active game flow
    return;
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
        gameState.players[id].justPerformedHardDrop = false;
        
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
        // Only update game state for active players
        updateGameState();
        
        // Create a completely fresh state object for active players with deep cloning
        // to prevent any shared references between objects
        const updatedGameStateForActive = {
          appPhase: gameState.appPhase,
          gameInProgress: gameState.gameInProgress,
          board: JSON.parse(JSON.stringify(gameState.board)),
          players: {},
          readyPlayers: [...gameState.readyPlayers],
          activePlayers: new Set(gameState.activePlayers),
          gameMode: gameState.gameMode,
          lineClearActive: gameState.lineClearActive,
          lineClearTimer: gameState.lineClearTimer,
          linesToClear: gameState.linesToClear ? [...gameState.linesToClear] : []
        };
        
        // Only include active players in the filtered state
        readyPlayers.forEach(id => {
          if (gameState.players[id]) {
            updatedGameStateForActive.players[id] = JSON.parse(JSON.stringify(gameState.players[id]));
          }
        });
        
        // Send filtered state to active players
        readyPlayers.forEach(id => {
          const socket = io.sockets.sockets.get(id);
          if (socket) {
            socket.emit('gameState', updatedGameStateForActive);
          }
        });
        
        // For non-ready players, continuously send the limited state
        // to ensure they stay on the homescreen with "Game in Progress" message
        nonReadyPlayers.forEach(id => {
          const socket = io.sockets.sockets.get(id);
          if (socket) {
            socket.emit('gameState', limitedState);
          }
        });
      }, FRAME_DELAY);
    }
  });

  // Handle player actions
  socket.on('playerAction', (action) => {
    // Only process actions from players who are:
    // 1. Playing in an active game
    // 2. Part of the active players set
    // 3. Were in the ready players list when the game started
    if (gameState.appPhase === 'playing' && 
        gameState.activePlayers.has(socket.id) &&
        gameState.readyPlayers.includes(socket.id)) {
      gameState = handlePlayerAction(gameState, socket.id, action);
    } else {
      console.log(`Ignored action from non-active player: ${socket.id}`);
    }
  });

  // Handle player disconnects
  socket.on('disconnect', () => {
    console.log(`Player disconnected: ${socket.id}`);
    gameState = handleDisconnect(gameState, socket.id);
    io.emit('gameState', gameState);
  });
});

// Start server
const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`Tetris server running on port ${PORT}`);
});