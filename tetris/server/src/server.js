// server/src/server.js
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const {
  createGameState,
  handleNewPlayer,
  handleDisconnect,
  handlePlayerAction,
  isValidMove,
  isValidMoveOnBoard, // Add this import
  getRandomTetromino,
  placeTetromino,
  clearLines,
  createEmptyBoard
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
  
  // Start entry delay for new piece
  player.isWaitingForNextPiece = true;
  player.entryDelayTimer = 0;
  
  // IMPROVED: Collect affected players first to avoid recursive calls
  const playersToLock = [];
  
  Object.keys(gameState.players).forEach(otherPlayerId => {
    if (otherPlayerId !== playerId) {
      const otherPlayer = gameState.players[otherPlayerId];
      
      // Skip players waiting for a new piece
      if (otherPlayer.isWaitingForNextPiece) return;
      
      // Check if this player's piece is now in an invalid position
      if (!isValidMove(gameState.board, otherPlayer.currentPiece, otherPlayer.x, otherPlayer.y, otherPlayerId, gameState.players)) {
        console.log(`Collision detected for player ${otherPlayerId} after piece lock`);
        playersToLock.push(otherPlayerId);
      }
    }
  });
  
  // Now lock the affected pieces in sequence
  playersToLock.forEach(idToLock => {
    const playerToLock = gameState.players[idToLock];
    
    // Place the piece directly without recursive call
    gameState.board = placeTetromino(gameState.board, playerToLock.currentPiece, playerToLock.x, playerToLock.y, idToLock);
    
    // Start entry delay for new piece
    playerToLock.isWaitingForNextPiece = true;
    playerToLock.entryDelayTimer = 0;
    
    console.log(`Forced lock for player ${idToLock}`);
  });
  
  // If any lines were cleared during force locking, process them
  if (playersToLock.length > 0) {
    const { newBoard: updatedBoard, linesCleared: additionalLines } = clearLines(gameState);
    gameState.board = updatedBoard;
    
    // Distribute points to the original player who caused the lock chain
    if (additionalLines > 0) {
      player.score += additionalLines * 100;
      console.log(`Player ${playerId} got ${additionalLines} additional lines from chain reaction`);
    }
  }
}

let gameLoop;

function updateGameState() {
  // Handle line clear animations
  if (gameState.lineClearActive) {
    gameState.lineClearTimer++;
    
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
    }
    
    // Skip other game updates during line clear
    return;
  }

  // Helper function to check if a piece is touching the ground or locked pieces only
  // (ignores collisions with other player's active pieces)
  function isTouchingGround(board, piece, x, y, playerId) {
    // Check if the piece would collide with the bottom or with locked pieces
    for (let r = 0; r < piece.shape.length; r++) {
      for (let c = 0; c < piece.shape[r].length; c++) {
        if (piece.shape[r][c]) {
          const boardY = y + r + 1; // Position below current cell
          const boardX = x + c;
          
          // Check if touching bottom
          if (boardY >= board.length) {
            return true;
          }
          
          // Check if touching another piece on the board (locked piece)
          if (board[boardY] && board[boardY][boardX] !== 0) {
            return true;
          }
        }
      }
    }
    return false;
  }

  // Helper function to reset player state
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
    player.fallSpeed = 45; // Normal speed
    player.softDropSpeed = 5; // Fast speed when soft dropping
    player.fallTimer = 0;
    
    return gameState;
  }

  // Process each player
  Object.keys(gameState.players).forEach(playerId => {
    const player = gameState.players[playerId];
    
    // Handle entry delay for new pieces
    if (player.isWaitingForNextPiece) {
      player.entryDelayTimer++;
      
    // In the updateGameState function where it checks for game over
    if (player.entryDelayTimer >= ENTRY_DELAY) {
      // Spawn new piece after delay
      player.currentPiece = getRandomTetromino();
      player.x = 4;
      player.y = 0;
      player.isWaitingForNextPiece = false;
      console.log(`New piece spawned for player ${playerId}: ${player.currentPiece.type}`);
      
      // CHANGE THIS LINE: Only check for collisions with the board and locked pieces, 
      // not with other players' active pieces
      if (!isValidMoveOnBoard(gameState.board, player.currentPiece, player.x, player.y, playerId)) {
          console.log(`Game over for player ${playerId}`);
          
          // Trigger game over state
          gameState.appPhase = 'gameover';
          
          // Send game over notification
          io.emit('gameOver', {
            playerId: playerId,
            score: player.score
          });
    
          // Set timeout to return to homescreen after 5 seconds
          setTimeout(() => {
            // Stop the game loop
            clearInterval(gameLoop);
            
            // Reset game state
            gameState.appPhase = 'homescreen';
            gameState.readyPlayers = [];
            gameState.board = createEmptyBoard(20, 10);
            
            // Reset all players
            Object.keys(gameState.players).forEach(id => {
              const p = gameState.players[id];
              p.isReady = false;
              p.isWaitingForNextPiece = false;
              p.currentPiece = getRandomTetromino();
              p.x = 4;
              p.y = 0;
              p.score = 0;
            });
            
            // Emit updated state
            io.emit('gameState', gameState);
            
            // Restart a simplified game loop for the homescreen
            gameLoop = setInterval(() => {
              io.emit('gameState', gameState);
            }, FRAME_DELAY);
          }, 5000);
          
          return;
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
            // Try to move left - including checking other player pieces
            if (isValidMove(gameState.board, player.currentPiece, player.x - 1, player.y, playerId, gameState.players)) {
              player.x -= 1;
            }
          } else if (player.dasDirection === 'right') {
            // Try to move right - including checking other player pieces
            if (isValidMove(gameState.board, player.currentPiece, player.x + 1, player.y, playerId, gameState.players)) {
              player.x += 1;
            }
          }
          
          // Reset repeat timer
          player.dasRepeatTimer = 0;
        }
      }
    }
    
    // Regular falling logic
    player.fallTimer = (player.fallTimer || 0) + 1;
    
    // First check if the piece can fall without hitting the ground or locked pieces
    const isTouchingFloorOrLockedPiece = isTouchingGround(gameState.board, player.currentPiece, player.x, player.y, playerId);
    
    // Second check if the piece would collide with another player's piece
    const canFallWithoutCollision = isValidMove(gameState.board, player.currentPiece, player.x, player.y + 1, playerId, gameState.players);
    
    if (!isTouchingFloorOrLockedPiece && canFallWithoutCollision) {
      // Piece can still fall
      if (player.fallTimer >= player.fallSpeed) {
        player.y += 1;
        player.fallTimer = 0;
        
        // Reset lock state since we're not touching ground
        player.isLocking = false;
        player.lockTimer = 0;
      }
    } else if (isTouchingFloorOrLockedPiece) {
      // Only start locking if touching ground or locked pieces, NOT other players' active pieces
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
    } else {
      // The piece can't fall but it's not touching ground (must be hitting another player's piece)
      // Don't lock, just wait (pieces can hover in mid-air if blocked by other pieces)
      player.fallTimer = 0;
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

  // Update the playerReady event handler
  socket.on('playerReady', (isReady) => {
    console.log(`Player ${socket.id} ready state: ${isReady}`);
    const player = gameState.players[socket.id];
    if (player) {
      player.isReady = isReady;
      
      // Make sure we're using socket.id not player.id (which is shortened)
      // Update ready players list
      if (isReady) {
        // Only add if not already in the list
        if (!gameState.readyPlayers.includes(socket.id)) {
          gameState.readyPlayers.push(socket.id);
        }
      } else {
        gameState.readyPlayers = gameState.readyPlayers.filter(id => id !== socket.id);
      }
      
      console.log('Ready players:', gameState.readyPlayers);
      io.emit('gameState', gameState);
    }
  });
  
  // Listen for game mode changes (only player 1 can change this)
  socket.on('setGameMode', (mode) => {
    const player = gameState.players[socket.id];
    if (player && player.playerNumber === 1) {
      console.log(`Game mode changed to: ${mode}`);
      gameState.gameMode = mode;
      io.emit('gameState', gameState);
    }
  });
  
  socket.on('startGame', () => {
    const player = gameState.players[socket.id];
    if (player && player.playerNumber === 1) {
      console.log('Game started by player 1');
      gameState.appPhase = 'playing';
      
      // Reset the board before starting
      gameState.board = createEmptyBoard(20, 10);
      
      // Reset all player scores and positions
      Object.keys(gameState.players).forEach(id => {
        if (gameState.readyPlayers.includes(id)) {
          const p = gameState.players[id];
          p.score = 0;
          p.x = 4;
          p.y = 0;
          p.currentPiece = getRandomTetromino();
          p.isWaitingForNextPiece = false;
          p.isLocking = false;
          p.lockTimer = 0;
          p.fallTimer = 0;
        }
      });
      
      // Stop any existing game loop
      clearInterval(gameLoop);
      
      // Start the full game loop again
      gameLoop = setInterval(() => {
        updateGameState();
        io.emit('gameState', gameState);
      }, FRAME_DELAY);
      
      io.emit('gameState', gameState);
    }
  });

  // Listen for actions from this player
  socket.on('playerAction', (action) => {
    // Only process actions if we're in the playing phase
    if (gameState.appPhase === 'playing') {
      console.log(`Player ${socket.id} action:`, action);
      gameState = handlePlayerAction(gameState, socket.id, action);
      io.emit('gameState', gameState);
    }
  });

  // Handle player disconnects
  socket.on('disconnect', () => {
    console.log(`Client disconnected: ${socket.id}`);
    
    // Remove from ready players if present
    gameState.readyPlayers = gameState.readyPlayers.filter(id => id !== socket.id);
    
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
//startGameLoop();s