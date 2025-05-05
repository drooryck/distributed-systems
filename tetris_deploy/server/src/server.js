const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const cors = require('cors');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const ClusterManager = require('./clusterManager');

// Parse server ID from command line arguments
const SERVER_ID = parseInt(process.argv[2] || '0', 10);

// In test environment, use a different port range or 0 for auto-assignment
const BASE_PORT = process.env.NODE_ENV === 'test' ? 0 : 3001;
const PORT = process.env.PORT || (BASE_PORT === 0 ? 0 : BASE_PORT + parseInt(SERVER_ID || '0'));

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

// Add leader redirection middleware - this routes all clients to the leader
app.use((req, res, next) => {
  // Skip redirect for API endpoints and status/control paths
  if (req.path.startsWith('/api') || req.path === '/status' || req.path === '/kill') {
    return next();
  }
  
  // If cluster is active and this is not the leader, redirect to leader
  if (clusterManager && !clusterManager.isLeaderServer()) {
    const leaderConfig = clusterManager.getLeaderConfig();
    if (leaderConfig) {
      const leaderUrl = `http://${leaderConfig.host}:${leaderConfig.port}${req.path}`;
      debugLog('cluster', `Redirecting client to leader at: ${leaderUrl}`);
      return res.redirect(303, leaderUrl);
    }
  }
  
  // Continue normal processing if we are the leader or standalone
  next();
});

// Serve static files from client build
app.use(express.static(path.join(__dirname, '../../client/build')));

// Ensure client HTML is served for all routes not explicitly handled
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../../client/build/index.html'));
});

// Initialize Socket.IO with CORS settings
const io = socketIO(server, {
  cors: {
    origin: [
      "https://tetristributed.vercel.app.vercel.app", 
      "https://distributed-systems-soww.onrender.com",
      "*" // For development
    ],
    methods: ["GET", "POST"],
    credentials: true
  }
});

// Initialize cluster manager
let clusterManager = null;
try {
  clusterManager = new ClusterManager(SERVER_ID);
  console.log(`Initialized cluster manager for server ${SERVER_ID}`);
} catch (error) {
  console.error('Failed to initialize cluster manager:', error);
}

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
  gameState: true,
  cluster: true
};

function debugLog(type, message, data) {
  if (DEBUG[type]) {
    console.log(`[SERVER ${SERVER_ID}:${type}] ${message}`, data !== undefined ? data : '');
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

// Helper function to convert activePlayers to array for network transmission
function activePlayersToArray(gameState) {
  if (!gameState) return gameState;
  
  // Clone the gameState to avoid modifying the original
  const networkGameState = {...gameState};
  
  // Convert Set to Array for network transmission
  if (networkGameState.activePlayers instanceof Set) {
    networkGameState.activePlayers = Array.from(networkGameState.activePlayers);
  }
  
  return networkGameState;
}

// Helper function to get activePlayers as a Set for internal use
function getActivePlayersAsSet(gameState) {
  if (!gameState || !gameState.activePlayers) return new Set();
  
  // If already a Set, return it
  if (gameState.activePlayers instanceof Set) {
    return gameState.activePlayers;
  }
  
  // Convert array or object to Set
  return new Set(Array.isArray(gameState.activePlayers) 
    ? gameState.activePlayers 
    : Object.keys(gameState.players || {}));
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
  
  /* ── LINE-CLEAR ANIMATION ────────────────────────────────────── */
  if (gameState.lineClearActive) {
    gameState.lineClearTimer++;

    if (gameState.lineClearTimer >= 30) {          // flash finished
      const cleared      = [...gameState.linesToClear].sort((a, b) => a - b);
      const cols         = gameState.board[0].length;
      const emptyRow     = () => new Array(cols).fill(0);

      /* deep-copy board to avoid aliasing rows */
      const newBoard = gameState.board.map(row => [...row]);

      /* remove cleared rows, then grow fresh rows on top           */
      for (let i = cleared.length - 1; i >= 0; --i) {
        newBoard.splice(cleared[i], 1);
      }
      for (let i = 0; i < cleared.length; ++i) {
        newBoard.unshift(emptyRow());
      }
      gameState.board = newBoard;

      /* shift every *active* player that’s above the removed lines */
      for (const pid of gameState.activePlayers) {
        const p = gameState.players[pid];
        if (!p || !p.currentPiece || p.isWaitingForNextPiece) continue;

        // how many cleared rows were *below* the piece’s top edge?
        const delta = cleared.filter(r => r > p.y).length;
        if (delta === 0) continue;

        p.y += delta; // keep visual/world position consistent

        /* clamp / re-validate so we never clip into locked cells   */
        while (!isValidMoveOnBoard(gameState.board, p.currentPiece, p.x, p.y)) {
          p.y--;                     // move back up until it fits
          if (p.y < -4) break;       // (-4 is safe sentinel)
        }
      }

      // reset animation flags
      gameState.lineClearActive = false;
      gameState.linesToClear    = [];
      gameState.lineClearTimer  = 0;
    }
  }
  /* ── END line-clear section ───────────────────────────────────── */
  
  // Process each active player - ensure we have a Set for iteration
  const activePlayers = getActivePlayersAsSet(gameState);
  Array.from(activePlayers).forEach(playerId => {
    const player = gameState.players[playerId];
    if (!player || !player.currentPiece) return;
    
    // Handle entry delay for new pieces
    if (player.isWaitingForNextPiece) {
      player.entryDelayTimer++;
      
      if (player.entryDelayTimer >= ENTRY_DELAY) {
        // Spawn new piece after delay
        player.currentPiece = getRandomTetromino();
        
        // Use player's specific spawn position instead of hardcoded position
        const playerIndex = Array.from(activePlayers).indexOf(playerId);
        const spawnPos = getSpawnPosition(playerIndex, gameState.board[0].length, activePlayers.size);
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
            
            // Calculate total score and determine if multiplayer
            const playerCount = gameState.activePlayers.size;
            const isMultiplayer = playerCount > 1;
            
            // Sum up all player scores
            let totalScore = 0;
            for (const pid of gameState.activePlayers) {
              if (gameState.players[pid] && typeof gameState.players[pid].score === 'number') {
                totalScore += gameState.players[pid].score;
              }
            }
            
            // Send game over event to room with enhanced data
            io.to(roomCode).emit('gameOver', { 
              playerId, 
              score: player.score,
              totalScore: totalScore,
              isMultiplayer: isMultiplayer,
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
        if (player.isSoftDropping) player.score += 1;
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
  
  // If we're the leader, replicate state to followers after update
  // Convert Set to Array for network transmission
  if (clusterManager && clusterManager.isLeaderServer()) {
    const networkGameState = activePlayersToArray(gameState);
    
    clusterManager.broadcastState({
      action: 'gameStateUpdate',
      roomCode,
      gameState: networkGameState,
      timestamp: Date.now()
    });
  }
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

// Socket.IO connection handler
io.on('connection', (socket) => {
  debugLog('events', `New client connected: ${socket.id}`);
  
  // Check if the server is the leader
  socket.on('checkLeader', (data, callback) => {
    const isLeader = clusterManager ? clusterManager.isLeaderServer() : true;
    callback({ isLeader });
  });

  // Create new room
  socket.on('createRoom', (data) => {
    const playerName = typeof data === 'string' ? data : data.playerName || 'Player';
    const roomCode = createRoom(socket.id, playerName);
    
    // Join the socket to the room
    socket.join(roomCode);
    socket.roomCode = roomCode;
    
    // Notify the client with initial game state
    const room = rooms[roomCode];
    
    // Ensure the appPhase is set to 'readyscreen'
    room.gameState.appPhase = 'readyscreen';
    
    debugLog('events', `Room ${roomCode} created by ${socket.id} (${playerName})`);
    
    // Send roomCreated event with room details
    io.to(socket.id).emit('roomCreated', {
      roomCode,
      playerName,
      gameState: room.gameState
    });
    
    // Save session data for the player for potential reconnection
    io.to(socket.id).emit('saveSession', {
      roomCode,
      playerName,
      socketId: socket.id
    });
  });

  // Join existing room
  socket.on('joinRoom', (data) => {
    const roomCode = data.roomCode.toUpperCase();
    const playerName = data.playerName || 'Player';
    
    debugLog('events', `Player ${socket.id} (${playerName}) attempting to join room ${roomCode}`);
    
    // Check if room exists
    if (!rooms[roomCode]) {
      socket.emit('error', { message: 'Room not found' });
      return;
    }
    
    // Check if game is already in progress
    const room = rooms[roomCode];
    if (room.gameState.appPhase === 'playing') {
      socket.emit('error', { message: 'Game already in progress' });
      return;
    }
    
    // Join the socket to the room
    socket.join(roomCode);
    socket.roomCode = roomCode;
    
    // Add the player to the game state
    const updatedGameState = handleNewPlayer(room.gameState, socket.id);
    room.gameState = updatedGameState;
    
    // Add player name to their data
    room.gameState.players[socket.id].name = playerName;
    
    debugLog('events', `Player ${socket.id} (${playerName}) joined room ${roomCode}`);
    
    // Send roomJoined event with room details
    socket.emit('roomJoined', { 
      roomCode,
      playerName,
      gameState: room.gameState
    });
    
    // Notify other players
    socket.to(roomCode).emit('playerJoined', {
      playerId: socket.id,
      playerName: playerName,
      gameState: room.gameState
    });
    
    // Save session data for the player for potential reconnection
    socket.emit('saveSession', {
      roomCode,
      playerName,
      socketId: socket.id
    });
    
    // Update room activity
    room.lastActivity = Date.now();
  });

  // Rejoin room (for reconnection after server failure)
  socket.on('rejoinRoom', (data) => {
    const roomCode = data.roomCode.toUpperCase();
    const playerName = data.playerName || 'Player';
    const previousSocketId = data.previousSocketId || '';
    const wasReady = data.wasReady || false; // Track if player was ready before disconnection
    
    debugLog('events', `Player ${socket.id} (${playerName}) attempting to rejoin room ${roomCode}`);
    
    // Check if room exists
    if (!rooms[roomCode]) {
      // Try to recover room from global cluster state if available
      if (clusterManager) {
        // Fix: Use requestRoomFromLeader instead of getGlobalState which doesn't exist
        if (clusterManager.isLeaderServer()) {
          debugLog('events', `Room ${roomCode} not found locally and we are the leader`);
          socket.emit('error', { message: 'Room not found and could not be recovered' });
          return;
        } else {
          // If we're not the leader, try to request the room from the leader
          debugLog('events', `Requesting room ${roomCode} from leader for player rejoin`);
          clusterManager.requestRoomFromLeader(roomCode)
            .then(requestedRoom => {
              if (requestedRoom) {
                // Create room with the state from leader
                rooms[roomCode] = {
                  gameState: requestedRoom,
                  createdAt: Date.now(),
                  lastActivity: Date.now()
                };
                
                // Set up game loop for the recovered room
                roomGameLoops[roomCode] = setInterval(() => {
                  if (rooms[roomCode] && rooms[roomCode].gameState.activePlayers.size > 0) {
                    io.to(roomCode).emit('gameState', rooms[roomCode].gameState);
                  }
                }, FRAME_DELAY);
                
                // Now that we have the room, continue with rejoin process
                completeRejoinProcess();
                
                debugLog('rooms', `Room ${roomCode} recovered from leader for player rejoin`);
              } else {
                socket.emit('error', { message: 'Room not found on any server' });
              }
            })
            .catch(error => {
              debugLog('errors', `Error requesting room from leader: ${error.message}`);
              socket.emit('error', { message: 'Failed to recover room data' });
            });
          return; // Return early as the above process is async
        }
      } else {
        socket.emit('error', { message: 'Room not found' });
        return;
      }
    }
    
    // Complete the rejoin process now that we have the room
    completeRejoinProcess();
    
    function completeRejoinProcess() {
      const room = rooms[roomCode];
      
      // Join the socket to the room
      socket.join(roomCode);
      socket.roomCode = roomCode;
      
      // Check if the player was previously registered in the room
      let playerExists = false;
      
      // Check active players first
      for (const existingId in room.gameState.players) {
        const player = room.gameState.players[existingId];
        if (player && player.name === playerName) {
          playerExists = true;
          
          debugLog('events', `Player ${playerName} found in active players, updating socket ID`);
          
          // Remove old player instance but keep their state
          const oldPlayerState = {...room.gameState.players[existingId]};
          delete room.gameState.players[existingId];
          room.gameState.activePlayers.delete(existingId);
          
          // Update player with new socket ID but keep their state (score, etc)
          room.gameState.players[socket.id] = {
            ...oldPlayerState,
            id: socket.id.substring(0, 4)
          };
          room.gameState.activePlayers.add(socket.id);
          break;
        }
      }
      
      // If player was not active, check disconnected players
      if (!playerExists && room.gameState.disconnectedPlayers) {
        for (const existingId in room.gameState.disconnectedPlayers) {
          const player = room.gameState.disconnectedPlayers[existingId];
          if (player && player.name === playerName) {
            playerExists = true;
            
            debugLog('events', `Player ${playerName} found in disconnected players, restoring state`);
            
            // Restore player from disconnected state
            room.gameState.players[socket.id] = {
              ...player,
              id: socket.id.substring(0, 4)
            };
            room.gameState.activePlayers.add(socket.id);
            
            // Remove from disconnected players
            delete room.gameState.disconnectedPlayers[existingId];
            break;
          }
        }
      }
      
      // If the player was not found at all, add them as new
      if (!playerExists) {
        // Add the player to the game state as a new player
        const updatedGameState = handleNewPlayer(room.gameState, socket.id);
        room.gameState = updatedGameState;
        
        // Add player name to their data
        room.gameState.players[socket.id].name = playerName;
        
        debugLog('events', `Player ${playerName} not found in room, added as new player`);
      }
      
      // Restore ready status if player was ready before
      if (wasReady && room.gameState.appPhase === 'readyscreen') {
        room.gameState.players[socket.id].isReady = true;
        if (!room.gameState.readyPlayers.includes(socket.id)) {
          room.gameState.readyPlayers.push(socket.id);
        }
        debugLog('events', `Restored ready status for reconnected player ${socket.id}`);
      }
      
      debugLog('events', `Player ${socket.id} (${playerName}) rejoined room ${roomCode}`);
      
      // Send roomRejoined event with room details
      socket.emit('roomRejoined', { 
        roomCode,
        playerName,
        gameState: room.gameState
      });
      
      // Notify other players
      socket.to(roomCode).emit('playerRejoined', {
        playerId: socket.id,
        playerName: playerName,
        gameState: room.gameState
      });
      
      // Save updated session data
      socket.emit('saveSession', {
        roomCode,
        playerName,
        socketId: socket.id
      });
      
      // Update room activity
      room.lastActivity = Date.now();
    }
  });

  // Leave room
  socket.on('leaveRoom', () => {
    leaveRoom(socket);
    
    // Send the player back to the home screen
    socket.emit('roomLeft', {
      appPhase: 'homescreen'
    });
  });

  // Mark player as ready
  socket.on('ready', () => {
    const roomCode = socket.roomCode;
    if (!roomCode || !rooms[roomCode]) {
      socket.emit('error', { message: 'Room not found' });
      return;
    }
    
    // Toggle player ready state
    const room = rooms[roomCode];
    const player = room.gameState.players[socket.id];
    if (player) {
      // Toggle ready state
      player.isReady = !player.isReady;
      
      if (player.isReady) {
        // Add to ready players if becoming ready
        if (!room.gameState.readyPlayers.includes(socket.id)) {
          room.gameState.readyPlayers.push(socket.id);
        }
      } else {
        // Remove from ready players if becoming unready
        room.gameState.readyPlayers = room.gameState.readyPlayers.filter(id => id !== socket.id);
      }
      
      debugLog('events', `Player ${socket.id} ${player.isReady ? 'ready' : 'unready'} in room ${roomCode}`);
      
      // Notify all players in the room
      io.to(roomCode).emit('playerReady', { 
        playerId: socket.id,
        gameState: room.gameState
      });
    }
    
    // Update room activity
    room.lastActivity = Date.now();
  });

  // Start game (host only)
  socket.on('startGame', () => {
    const roomCode = socket.roomCode;
    if (!roomCode || !rooms[roomCode]) {
      socket.emit('error', { message: 'Room not found' });
      return;
    }
    
    // Only the host can start the game
    const room = rooms[roomCode];
    const player = room.gameState.players[socket.id];
    if (!player || !player.isHost) {
      socket.emit('error', { message: 'Only the host can start the game' });
      return;
    }
    
    // Make sure there are ready players
    if (room.gameState.readyPlayers.length === 0) {
      socket.emit('error', { message: 'No players are ready' });
      return;
    }
    
    debugLog('events', `Host ${socket.id} starting game in room ${roomCode}`);
    startGame(roomCode);
  });

  // Player in-game action
  socket.on('playerAction', (action) => {
    const roomCode = socket.roomCode;
    if (!roomCode || !rooms[roomCode]) return;
    
    // Handle action
    const room = rooms[roomCode];
    const gameState = handlePlayerAction(room.gameState, socket.id, action);
    room.gameState = gameState;
    
    // Update room activity
    room.lastActivity = Date.now();
  });

  // Request initial state (used after reconnection)
  socket.on('requestInitialState', () => {
    // First check if we're in a reconnection flow by looking at the request headers
    const reconnecting = socket.handshake.query && socket.handshake.query.rejoin === 'true';
    
    if (socket.roomCode) {
      const room = rooms[socket.roomCode];
      if (room) {
        socket.emit('gameState', room.gameState);
      }
    } else if (reconnecting) {
      // Don't emit homescreen state - this will give client time to attempt roomRejoin
      console.log(`Client ${socket.id} reconnecting, holding homescreen state until rejoin attempt`);
    } else {
      console.log(`2`);
      // Normal flow - send homescreen
      socket.emit('init', {
        appPhase: 'homescreen',
        socketId: socket.id
      });
    }
  });

  // Disconnect handler
  socket.on('disconnect', () => {
    debugLog('events', `Client disconnected: ${socket.id}`);
    leaveRoom(socket);
  });
});

// Start server
server.listen(PORT, '0.0.0.0', () => {
  console.log(`Tetris server ${SERVER_ID} running on port ${PORT}`);
  
  // Initialize cluster manager after server is running
  if (clusterManager) {
    clusterManager.initialize();
    
    // Listen for leadership changes
    clusterManager.on('became-leader', () => {
      console.log(`Server ${SERVER_ID} became the leader`);
      
      // Send server status to all connected clients
      io.emit('server-status', { 
        isLeader: true, 
        serverId: SERVER_ID 
      });
      
      // Set up periodic full state replication to followers
      const stateReplicationInterval = setInterval(() => {
        if (clusterManager.isLeaderServer()) {
          clusterManager.broadcastFullGameState(rooms);
        } else {
          // If no longer leader, clear the interval
          clearInterval(stateReplicationInterval);
        }
      }, 3000); // Replicate every 3 seconds
      
      // Restart game loops for active rooms using the helper function
      Object.keys(rooms).forEach(roomCode => {
        if (rooms[roomCode].gameState.appPhase === 'playing') {
          debugLog('cluster', `Leader restarting game loop for room ${roomCode}`);
          
          // Use the helper function to restart the game loop properly
          restartGameLoopAsLeader(roomCode);
        }
      });
    });
    
    clusterManager.on('stepped-down', () => {
      console.log(`Server ${SERVER_ID} is no longer the leader`);
      
      // Send server status to all connected clients
      io.emit('server-status', { 
        isLeader: false, 
        serverId: SERVER_ID 
      });
    });
    
    // Listen for state updates from leader
    clusterManager.on('state-update', (data) => {
      if (data.action === 'roomCreated' && data.roomCode && data.gameState) {
        // Convert activePlayers to Set using our new function
        const gameStateWithSet = data.gameState;
        if (gameStateWithSet.activePlayers) {
          gameStateWithSet.activePlayers = getActivePlayersAsSet(gameStateWithSet);
        }
        
        // Replicate room creation from leader
        rooms[data.roomCode] = {
          gameState: gameStateWithSet,
          createdAt: Date.now(),
          lastActivity: Date.now()
        };
        
        debugLog('cluster', `Replicated room ${data.roomCode} from leader`);
      } 
      else if (data.action === 'fullStateSync' && data.rooms) {
        // Handle complete state sync from leader
        Object.keys(data.rooms).forEach(roomCode => {
          const roomData = data.rooms[roomCode];
          
          // Convert activePlayers back to a Set using our new function
          if (roomData.gameState && roomData.gameState.activePlayers) {
            roomData.gameState.activePlayers = getActivePlayersAsSet(roomData.gameState);
          }
          
          if (!rooms[roomCode]) {
            // This is a new room we didn't have
            rooms[roomCode] = {
              gameState: roomData.gameState,
              createdAt: roomData.createdAt || Date.now(),
              lastActivity: roomData.lastActivity || Date.now()
            };
            debugLog('cluster', `Added new room ${roomCode} from full state sync`);
          } else {
            // Update existing room state
            rooms[roomCode].gameState = roomData.gameState;
            rooms[roomCode].lastActivity = roomData.lastActivity;
          }
          
          // Make sure game loop is properly set up for this room
          // But don't start duplicate loops
          if (roomData.gameState.appPhase === 'playing' && !roomGameLoops[roomCode]) {
            roomGameLoops[roomCode] = setInterval(() => {
              if (!rooms[roomCode]) {
                clearInterval(roomGameLoops[roomCode]);
                return;
              }
              
              // For followers, just send the state without updating it
              io.to(roomCode).emit('gameState', rooms[roomCode].gameState);
            }, FRAME_DELAY);
          }
        });
        
        debugLog('cluster', `Completed full state sync from leader with ${Object.keys(data.rooms).length} rooms`);
      }
      else if (data.action === 'gameStateUpdate' && data.roomCode && data.gameState) {
        // Handle real-time game state updates
        
        // Convert activePlayers back to a Set using our new function
        if (data.gameState && data.gameState.activePlayers) {
          data.gameState.activePlayers = getActivePlayersAsSet(data.gameState);
        }
        
        if (rooms[data.roomCode]) {
          // Update the game state for this room
          rooms[data.roomCode].gameState = data.gameState;
          rooms[data.roomCode].lastActivity = Date.now();
          
          // Make sure we have the correct game loop setup
          const appPhase = data.gameState.appPhase;
          
          // Only update followers' connected clients if they exist
          // This prevents errors when players are only connected to the leader
          const roomSocketIds = io.sockets.adapter.rooms.get(data.roomCode);
          if (roomSocketIds && roomSocketIds.size > 0) {
            io.to(data.roomCode).emit('gameState', data.gameState);
            debugLog('cluster', `Sent real-time game state update for room ${data.roomCode} to ${roomSocketIds.size} clients`);
          }
        } else {
          // We don't have this room yet, create it
          rooms[data.roomCode] = {
            gameState: data.gameState,
            createdAt: Date.now(),
            lastActivity: Date.now()
          };
          debugLog('cluster', `Created new room ${data.roomCode} from real-time update`);
        }
      }
    });
  }
});

// Helper function to properly restart game loops when becoming leader
function restartGameLoopAsLeader(roomCode) {
  if (!rooms[roomCode] || rooms[roomCode].gameState.appPhase !== 'playing') {
    return false;
  }
  
  // Clear any existing game loop
  if (roomGameLoops[roomCode]) {
    clearInterval(roomGameLoops[roomCode]);
  }
  
  // Create a new game loop that updates the state (only leader does this)
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
  
  debugLog('cluster', `Leader established game loop for room ${roomCode}`);
  return true;
}

// Add a route for server status - useful for testing
app.get('/status', (req, res) => {
  const isLeader = clusterManager ? clusterManager.isLeaderServer() : true;
  const leaderId = clusterManager ? clusterManager.getLeaderId() : SERVER_ID;
  
  res.json({
    serverId: SERVER_ID,
    port: PORT,
    isLeader,
    leaderId,
    connectedServers: clusterManager ? Object.keys(clusterManager.connections) : [],
    rooms: Object.keys(rooms),
    uptime: process.uptime()
  });
});

// Add an endpoint to gracefully kill the server for testing
app.post('/kill', (req, res) => {
  console.log(`Server ${SERVER_ID} shutting down by request`);
  res.send('Server shutting down');
  
  // Clean up and exit after a short delay to allow response to be sent
  setTimeout(() => {
    if (clusterManager) {
      clusterManager.shutdown();
    }
    process.exit(0);
  }, 500);
});