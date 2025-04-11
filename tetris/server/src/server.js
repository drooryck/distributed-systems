// server/src/server.js
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const {
  createGameState,
  handleNewPlayer,
  handleDisconnect,
  handlePlayerAction,
  isValidMove,  // Make sure to export this from gameState.js
  getRandomTetromino,
  placeTetromino,
  clearLines
} = require('./gameState');

// Constants for game mechanics
const FRAME_RATE = 60;
const FRAME_DELAY = 1000 / FRAME_RATE; // ~16.67ms
const LOCK_DELAY = 30; // 30 frames (0.5 seconds)
const DAS_DELAY = 12; // 12 frames before auto-repeat
const DAS_REPEAT = 2; // 2 frames between repeats
const LINE_CLEAR_DELAY = 30; // 30 frames (0.5 seconds) 3:30pm
const ENTRY_DELAY = 15; // 15 frames (0.25 seconds) - Add this line

// Create our initial game state (empty board, no players)
let gameState = createGameState();

// Modify piece locking function
function handlePieceLocking(gameState, playerId) {
  const player = gameState.players[playerId];
  
  // Place the current piece on the board
  gameState.board = placeTetromino(gameState.board, player.currentPiece, player.x, player.y, playerId);
  
  // Clear lines and update score
  const { newBoard, linesCleared } = clearLines(gameState);
  gameState.board = newBoard;
  player.score += linesCleared * 100;
  
  // Start entry delay
  player.isWaitingForNextPiece = true;
  player.entryDelayTimer = 0;
}

let gameLoop;

function updateGameState() {
  // Add to updateGameState at the top
  if (gameState.lineClearActive) {
    gameState.lineClearTimer++;
    
    // During animation, highlight the rows to be cleared
    // (This would be sent to clients for visual effect)
    
    if (gameState.lineClearTimer >= LINE_CLEAR_DELAY) {
      // Animation finished, actually clear the lines
      const newBoard = [...gameState.board];
      
      // Remove the cleared lines
      gameState.linesToClear.forEach(rowIndex => {
        newBoard.splice(rowIndex, 1);
        newBoard.unshift(new Array(gameState.board[0].length).fill(0));
      });
      
      gameState.board = newBoard;
      gameState.lineClearActive = false;
      gameState.linesToClear = [];
      
      // Now we can continue with normal gameplay
    }
    
    // Skip other game updates during line clear
    return;
  }

  function resetPlayer(gameState, playerId) {
    const player = gameState.players[playerId];
    if (!player) return gameState;
    
    player.currentPiece = getRandomTetromino();
    player.x = 4;
    player.y = 0;
    player.score = 0;
    player.lockTimer = 0;
    player.isLocking = false;
    player.lockResets = 0;
    
    return gameState;
  }

  Object.keys(gameState.players).forEach(playerId => {
    const player = gameState.players[playerId];
    
    if (player.isWaitingForNextPiece) {
      player.entryDelayTimer++;
      
      if (player.entryDelayTimer >= ENTRY_DELAY) {
        // Spawn new piece after delay
        player.currentPiece = getRandomTetromino();
        player.x = 4;
        player.y = 0;
        player.isWaitingForNextPiece = false;
        console.log(`New piece spawned for player ${playerId}: ${player.currentPiece.type}`);
        
        // Check for game over condition
        if (!isValidMove(gameState.board, player.currentPiece, player.x, player.y)) {
          console.log(`Game over for player ${playerId}`);
          resetPlayer(gameState, playerId);
        }
      }
      
      return; // Skip regular fall logic while waiting
    }
    
    // Handle DAS (Delayed Auto Shift)
    if (player.dasDirection) {
      player.dasTimer++;
      
      if (player.dasTimer >= DAS_DELAY) {
        // DAS activated, handle repeats
        player.dasRepeatTimer++;
        
        if (player.dasRepeatTimer >= DAS_REPEAT) {
          // Time for another movement
          if (player.dasDirection === 'left') {
            // Try to move left
            if (isValidMove(gameState.board, player.currentPiece, player.x - 1, player.y)) {
              player.x -= 1;
            }
          } else if (player.dasDirection === 'right') {
            // Try to move right
            if (isValidMove(gameState.board, player.currentPiece, player.x + 1, player.y)) {
              player.x += 1;
            }
          }
          
          // Reset repeat timer
          player.dasRepeatTimer = 0;
        }
      }
    }
    
    // Regular falling logic - ADD RIGHT HERE
    // Increment player's fall timer
    player.fallTimer = (player.fallTimer || 0) + 1;
    
    if (isValidMove(gameState.board, player.currentPiece, player.x, player.y + 1)) {
      // Piece can still fall
      if (player.fallTimer >= player.fallSpeed) {
        player.y += 1;
        player.fallTimer = 0;
        
        // Reset lock state since we're not touching ground
        player.isLocking = false;
        player.lockTimer = 0;
      }
    } else {
      // Piece is touching ground, start lock process
      if (!player.isLocking) {
        player.isLocking = true;
        player.lockTimer = 0;
      }
      
      player.lockTimer++;
      
      if (player.lockTimer >= LOCK_DELAY) {
        // Lock the piece and generate new one
        handlePieceLocking(gameState, playerId);
        player.isLocking = false;
      }
    }
  });
}

// make it pretty easy hopefully to avoid locking issues.
function startGameLoop() {
  gameLoop = setInterval(() => {
    // Update game state (piece falling, etc.)
    updateGameState();
    
    // Broadcast updated state to all clients
    io.emit('gameState', gameState);
  }, FRAME_DELAY);
}

// Create an Express app and an HTTP server
const app = express();
const server = http.createServer(app);

// Attach Socket.IO to the HTTP server
const io = new Server(server, {
  cors: {
    origin: "http://localhost:3000",
    methods: ["GET", "POST"]
  }
});

// Add a test endpoint
app.get('/test', (req, res) => {
  res.send('Server is running!');
});

io.on('connection', (socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Add this new player to our game state
  gameState = handleNewPlayer(gameState, socket.id);

  // Send the connecting player the current game state
  socket.emit('init', gameState);

  // Broadcast the updated state to all players
  io.emit('gameState', gameState);

  // Listen for actions from this player
  socket.on('playerAction', (action) => {
    console.log(`Player ${socket.id} action:`, action);
    gameState = handlePlayerAction(gameState, socket.id, action);
    io.emit('gameState', gameState);
  });

  // Handle player disconnects
  socket.on('disconnect', () => {
    console.log(`Client disconnected: ${socket.id}`);
    gameState = handleDisconnect(gameState, socket.id);
    io.emit('gameState', gameState);
  });
});

// Start the server
const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

// Start the game loop when the server starts
startGameLoop();