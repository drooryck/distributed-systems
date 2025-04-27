const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const cors = require('cors');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

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

// Debug configuration
const DEBUG = {
  rooms: true,
  events: true,
  gameState: true
};

function debugLog(type, message, data) {
  if (DEBUG[type]) {
    console.log(`[SERVER:${type}] ${message}`, data !== undefined ? data : '');
  }
}

// Room Management
const rooms = {}; // Store all active rooms
const roomGameLoops = {}; // Store game loop intervals by room code
const inactiveRoomCleanupTime = 1000 * 60 * 30; // 30 minutes

// Generate a 6-character room code (letters and numbers)
function generateRoomCode() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // Removed confusing chars like 0, O, 1, I
  let result = '';
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

// Create a new room
function createRoom(socketId, playerName) {
  // Generate a unique room code
  let roomCode;
  do {
    roomCode = generateRoomCode();
  } while (rooms[roomCode]);
  
  // Create new game state for the room
  const roomGameState = createGameState();
  roomGameState.roomCode = roomCode;
  roomGameState.appPhase = 'readyscreen'; // EXPLICITLY set this to readyscreen
  
  // Add the creator as the first player and host
  roomGameState.players = {}; // Clear any default players
  roomGameState.activePlayers = new Set([socketId]); // Initialize with creator
  roomGameState.readyPlayers = []; // No players ready yet
  
  // Add player to game state with host privileges
  roomGameState.players[socketId] = {
    id: socketId.substring(0, 4),
    playerNumber: 1,
    isHost: true, // First player is the host
    name: playerName || `Player 1`,
    isReady: false,
    color: roomGameState.playerColors[0],
    score: 0
  };
  
  // Store room in rooms object
  rooms[roomCode] = {
    gameState: roomGameState,
    createdAt: Date.now(),
    lastActivity: Date.now()
  };
  
  debugLog('rooms', `Room created: ${roomCode} by player ${socketId}, appPhase=${roomGameState.appPhase}`);
  
  // Start a simple game state update loop for this room
  roomGameLoops[roomCode] = setInterval(() => {
    // Only send updates if there are players in the room and the room still exists
    if (rooms[roomCode] && rooms[roomCode].gameState.activePlayers.size > 0) {
      // Don't override the appPhase - IMPORTANT fix
      const currentState = rooms[roomCode].gameState;
      
      // Send the current state without modifying anything
      // This ensures we don't reset appPhase accidentally
      io.to(roomCode).emit('gameState', currentState);
    }
  }, FRAME_DELAY);
  
  // Schedule cleanup for inactive rooms
  setTimeout(() => checkRoomActivity(roomCode), inactiveRoomCleanupTime);
  
  return roomCode;
}

// Check if a room is active and clean up if inactive
function checkRoomActivity(roomCode) {
  if (!rooms[roomCode]) return;
  
  const now = Date.now();
  const room = rooms[roomCode];
  
  // If no activity for 30 minutes and no active players, remove the room
  if (now - room.lastActivity > inactiveRoomCleanupTime && 
      room.gameState.activePlayers.size === 0) {
    cleanupRoom(roomCode);
    debugLog('rooms', `Cleaned up inactive room: ${roomCode}`);
  } else {
    // Schedule next check
    setTimeout(() => checkRoomActivity(roomCode), inactiveRoomCleanupTime);
  }
}

// Clean up a room
function cleanupRoom(roomCode) {
  if (roomGameLoops[roomCode]) {
    clearInterval(roomGameLoops[roomCode]);
    delete roomGameLoops[roomCode];
  }
  
  delete rooms[roomCode];
}

// Handle player leaving a room
function leaveRoom(socket) {
  const roomCode = socket.roomCode;
  if (!roomCode || !rooms[roomCode]) return;
  
  const room = rooms[roomCode];
  const players = room.gameState.players;
  
  // Remove player from ready players
  room.gameState.readyPlayers = room.gameState.readyPlayers.filter(id => id !== socket.id);
  
  // Remove player from active players
  room.gameState.activePlayers.delete(socket.id);
  
  // Record player leaving
  const leavingPlayer = players[socket.id];
  if (leavingPlayer) {
    const wasHost = leavingPlayer.isHost;
    
    // Remove player from players object
    delete players[socket.id];
    
    // Log the leave
    debugLog('rooms', `Player ${socket.id} left room ${roomCode}`);
    
    // Notify other players
    socket.to(roomCode).emit('playerLeft', {
      playerId: socket.id,
      gameState: room.gameState
    });
    
    // If room is empty, clean it up
    if (room.gameState.activePlayers.size === 0) {
      cleanupRoom(roomCode);
      debugLog('rooms', `Room ${roomCode} cleaned up after last player left`);
    } 
    // If player was host, assign host to the next player
    else if (wasHost) {
      const remainingPlayers = Object.keys(players);
      if (remainingPlayers.length > 0) {
        const newHostId = remainingPlayers[0];
        players[newHostId].isHost = true;
        
        // Notify the new host
        io.to(newHostId).emit('hostAssigned', {
          gameState: room.gameState
        });
        
        debugLog('rooms', `New host assigned in room ${roomCode}: ${newHostId}`);
      }
    }
  }
  
  // Update room last activity
  if (room) {
    room.lastActivity = Date.now();
  }
  
  // Remove socket from room
  socket.leave(roomCode);
  socket.roomCode = null;
}

// Start game in a room
function startGame(roomCode) {
  if (!rooms[roomCode]) return;
  
  const room = rooms[roomCode];
  room.gameState.appPhase = 'playing';
  room.gameState.gameInProgress = true;
  
  // Only use ready players for the game
  const readyPlayers = Object.keys(room.gameState.players).filter(id => 
    room.gameState.readyPlayers.includes(id));
  
  // Get the count of ONLY READY players
  const readyPlayerCount = readyPlayers.length;
  debugLog('rooms', `Starting game in room ${roomCode} with ${readyPlayerCount} ready players`);
  
  // Get board dimensions based on READY players only
  const { rows, cols } = getBoardDimensions(readyPlayerCount);
  room.gameState.board = createEmptyBoard(rows, cols);
  
  // Update activePlayers set with only ready players
  room.gameState.activePlayers = new Set(readyPlayers);
  
  // Initialize only ready players for the game
  readyPlayers.forEach((id, index) => {
    // Calculate spawn position
    const spawnPos = getSpawnPosition(index, cols, readyPlayerCount);
    
    // Initialize player state
    room.gameState.players[id].score = 0;
    room.gameState.players[id].x = spawnPos.x;
    room.gameState.players[id].y = spawnPos.y;
    room.gameState.players[id].currentPiece = getRandomTetromino();
    room.gameState.players[id].isWaitingForNextPiece = false;
    room.gameState.players[id].isLocking = false;
    room.gameState.players[id].lockTimer = 0;
    room.gameState.players[id].fallTimer = room.gameState.players[id].fallSpeed - 1;
    room.gameState.players[id].fallSpeed = 45; 
    room.gameState.players[id].softDropSpeed = 5;
    room.gameState.players[id].justPerformedHardDrop = false;
    
    debugLog('rooms', `Player ${id} (index ${index}) spawning at position (${spawnPos.x}, ${spawnPos.y})`);
  });
  
  // Update room activity
  room.lastActivity = Date.now();
  
  // Set up game loop for this room
  if (roomGameLoops[roomCode]) {
    clearInterval(roomGameLoops[roomCode]);
  }
  
  roomGameLoops[roomCode] = setInterval(() => {
    // Skip if room no longer exists
    if (!rooms[roomCode]) {
      clearInterval(roomGameLoops[roomCode]);
      return;
    }
    
    // Update game state for this room
    updateRoomGameState(roomCode);
    
    // Send game state to all players in room
    io.to(roomCode).emit('gameState', rooms[roomCode].gameState);
  }, FRAME_DELAY);
}

// Main game update function for a specific room
function updateRoomGameState(roomCode) {
  if (!rooms[roomCode]) return;
  
  const gameState = rooms[roomCode].gameState;
  
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
            debugLog('rooms', `Game over for player ${playerId} in room ${roomCode}`);
            gameState.appPhase = 'gameover';
            
            // Send game over event to room
            io.to(roomCode).emit('gameOver', { 
              playerId, 
              score: player.score,
              isCurrentPlayer: true
            });
          
            // Reset room after timeout
            setTimeout(() => resetRoom(roomCode), 5000);
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
  
  // Update room last activity time
  rooms[roomCode].lastActivity = Date.now();
}

// Reset room after game over
function resetRoom(roomCode) {
  if (!rooms[roomCode]) return;
  
  debugLog('rooms', `Resetting room ${roomCode}`);
  
  // Clear any existing game loop
  if (roomGameLoops[roomCode]) {
    clearInterval(roomGameLoops[roomCode]);
  }
  
  // Save connected players and their data
  const room = rooms[roomCode];
  const playerData = {};
  
  // Get all socket IDs in this room
  const socketsInRoom = io.sockets.adapter.rooms.get(roomCode) || new Set();
  
  Array.from(socketsInRoom).forEach(socketId => {
    if (room.gameState.players[socketId]) {
      // Save essential player data
      playerData[socketId] = {
        id: room.gameState.players[socketId].id,
        name: room.gameState.players[socketId].name,
        playerNumber: room.gameState.players[socketId].playerNumber,
        color: room.gameState.players[socketId].color,
        isHost: room.gameState.players[socketId].isHost
      };
    }
  });
  
  // Create fresh game state for the room
  const newGameState = createGameState();
  newGameState.roomCode = roomCode;
  newGameState.appPhase = 'readyscreen';
  newGameState.gameInProgress = false;
  newGameState.players = {};
  newGameState.activePlayers = new Set();
  newGameState.readyPlayers = [];
  
  // Re-add all connected players
  Array.from(socketsInRoom).forEach(socketId => {
    if (playerData[socketId]) {
      // Restore player with saved data
      newGameState.players[socketId] = {
        ...playerData[socketId],
        score: 0,
        isReady: false
      };
      newGameState.activePlayers.add(socketId);
    }
  });
  
  // Update room with new game state
  rooms[roomCode].gameState = newGameState;
  
  // Start a simple game state update loop
  roomGameLoops[roomCode] = setInterval(() => {
    if (rooms[roomCode] && rooms[roomCode].gameState.activePlayers.size > 0) {
      io.to(roomCode).emit('gameState', rooms[roomCode].gameState);
    }
  }, FRAME_DELAY);
  
  // Send updated game state to all players in room
  io.to(roomCode).emit('gameState', newGameState);
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

// Improved piece locking function for a specific room
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
          debugLog('rooms', `Collision detected for player ${otherPlayerId} after piece lock`);
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
    debugLog('rooms', `Forced lock for player ${idToLock}`);
  });
  
  // Handle lines cleared during force locking
  if (playersToLock.length > 0) {
    const { newBoard: updatedBoard, linesCleared: additionalLines } = clearLines(gameState);
    gameState.board = updatedBoard;
    
    if (additionalLines > 0) {
      player.score += additionalLines * 100;
      debugLog('rooms', `Player ${playerId} got ${additionalLines} additional lines from chain reaction`);
    }
  }
  
  return gameState;
}

// Handle Socket.IO connections
io.on('connection', (socket) => {
  debugLog('events', `Player connected: ${socket.id}`);
  
  // Send initial state with no room assigned yet
  socket.emit('init', { 
    appPhase: 'homescreen',
    socketId: socket.id
  });
  
  // Handle creating a room
  socket.on('createRoom', (playerName) => {
    // If player is already in a room, make them leave first
    if (socket.roomCode) {
      leaveRoom(socket);
    }
    
    // Create new room and add player
    const roomCode = createRoom(socket.id, playerName);
    socket.roomCode = roomCode;
    socket.join(roomCode); // Socket.IO room
    
    debugLog('rooms', `Player ${socket.id} created room ${roomCode}`);
    
    // Send room info to client
    socket.emit('roomCreated', { 
      roomCode,
      gameState: rooms[roomCode].gameState
    });
  });
  
  // Handle joining a room
  socket.on('joinRoom', ({ roomCode, playerName }) => {
    roomCode = roomCode.toUpperCase();
    
    // If player is already in a room, make them leave first
    if (socket.roomCode) {
      leaveRoom(socket);
    }
    
    // Check if room exists
    if (!rooms[roomCode]) {
      socket.emit('error', { message: 'Room not found.' });
      return;
    }
    
    // Check if game in progress
    if (rooms[roomCode].gameState.appPhase === 'playing') {
      socket.emit('error', { message: 'Game in progress. Please try another room.' });
      return;
    }
    
    // Add player to room
    socket.roomCode = roomCode;
    socket.join(roomCode); // Socket.IO room
    
    // Add player to room's game state
    rooms[roomCode].gameState = handleNewPlayer(rooms[roomCode].gameState, socket.id);
    
    // Set player name
    rooms[roomCode].gameState.players[socket.id].name = playerName || `Player ${rooms[roomCode].gameState.players[socket.id].playerNumber}`;
    
    debugLog('rooms', `Player ${socket.id} joined room ${roomCode}`);
    
    // Send room info to client
    socket.emit('roomJoined', { 
      roomCode,
      gameState: rooms[roomCode].gameState
    });
    
    // Notify other players in room
    socket.to(roomCode).emit('playerJoined', {
      playerId: socket.id,
      player: rooms[roomCode].gameState.players[socket.id],
      gameState: rooms[roomCode].gameState
    });
  });
  
  // Handle player leaving room
  socket.on('leaveRoom', () => {
    leaveRoom(socket);
    
    // Send the player back to the home screen
    socket.emit('roomLeft', {
      appPhase: 'homescreen'
    });
  });
  
  // Handle player ready state
  socket.on('playerReady', (isReady) => {
    const roomCode = socket.roomCode;
    if (!roomCode || !rooms[roomCode]) return;
    
    const gameState = rooms[roomCode].gameState;
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
    
    // Broadcast to room
    io.to(roomCode).emit('gameState', gameState);
  });
  
  // Handle game mode changes
  socket.on('setGameMode', (mode) => {
    const roomCode = socket.roomCode;
    if (!roomCode || !rooms[roomCode]) return;
    
    const gameState = rooms[roomCode].gameState;
    const player = gameState.players[socket.id];
    
    // Only host can change game mode
    if (player && player.isHost) {
      gameState.gameMode = mode;
      io.to(roomCode).emit('gameState', gameState);
    }
  });

  // Handle game start (only host can start)
  socket.on('startGame', () => {
    const roomCode = socket.roomCode;
    if (!roomCode || !rooms[roomCode]) return;
    
    const gameState = rooms[roomCode].gameState;
    const player = gameState.players[socket.id];
    
    // Only host can start the game
    if (player && player.isHost) {
      debugLog('rooms', `Game started in room ${roomCode} by host ${socket.id}`);
      startGame(roomCode);
    }
  });
  
  // Handle player actions
  socket.on('playerAction', (action) => {
    const roomCode = socket.roomCode;
    if (!roomCode || !rooms[roomCode]) return;
    
    const gameState = rooms[roomCode].gameState;
    
    // Only process actions from active players
    if (gameState.appPhase === 'playing' && 
        gameState.activePlayers.has(socket.id) &&
        gameState.readyPlayers.includes(socket.id)) {
      
      // Update the room's game state
      rooms[roomCode].gameState = handlePlayerAction(gameState, socket.id, action);
    } else {
      debugLog('rooms', `Ignored action from non-active player: ${socket.id} in room ${roomCode}`);
    }
  });

  // Handle player disconnects
  socket.on('disconnect', () => {
    debugLog('events', `Player disconnected: ${socket.id}`);
    
    // Handle room cleanup if player was in a room
    if (socket.roomCode) {
      leaveRoom(socket);
    }
  });
});

// Start server
const PORT = process.env.PORT || 3001;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`Tetris server running on port ${PORT}`);
});