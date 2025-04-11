// server/src/gameState.js

// Define tetromino shapes and colors
const TETROMINOES = {
  I: {
    shape: [
      [0, 0, 0, 0],
      [1, 1, 1, 1],
      [0, 0, 0, 0],
      [0, 0, 0, 0]
    ],
    color: 'cyan'
  },
  J: {
    shape: [
      [2, 0, 0],
      [2, 2, 2],
      [0, 0, 0]
    ],
    color: 'blue'
  },
  L: {
    shape: [
      [0, 0, 3],
      [3, 3, 3],
      [0, 0, 0]
    ],
    color: 'orange'
  },
  O: {
    shape: [
      [4, 4],
      [4, 4]
    ],
    color: 'yellow'
  },
  S: {
    shape: [
      [0, 5, 5],
      [5, 5, 0],
      [0, 0, 0]
    ],
    color: 'green'
  },
  T: {
    shape: [
      [0, 6, 0],
      [6, 6, 6],
      [0, 0, 0]
    ],
    color: 'purple'
  },
  Z: {
    shape: [
      [7, 7, 0],
      [0, 7, 7],
      [0, 0, 0]
    ],
    color: 'red'
  }
};

// Get a random tetromino type
function getRandomTetromino() {
  const types = Object.keys(TETROMINOES);
  const randomType = types[Math.floor(Math.random() * types.length)];
  return {
    type: randomType,
    ...TETROMINOES[randomType]
  };
}

function createGameState() {
  return {
    board: createEmptyBoard(20, 10),
    players: {}, // will map socket_id -> player data
    gameOver: false,
    playerColors: ['#FF5733', '#33FF57', '#3357FF', '#F3FF33'],
    lineClearActive: false,
    lineClearTimer: 0,
    linesToClear: []
  };
}

function createEmptyBoard(rows, cols) {
  const board = [];
  for (let r = 0; r < rows; r++) {
    board.push(new Array(cols).fill(0));
  }
  return board;
}

function handleNewPlayer(gameState, playerId) {
  // Assign a color from our color pool
  const colorIndex = Object.keys(gameState.players).length % gameState.playerColors.length;
  
  // Add a new player object to the state
  gameState.players[playerId] = {
    x: 4,       // Starting X position
    y: 0,       // Starting Y position
    score: 0,
    color: gameState.playerColors[colorIndex],
    currentPiece: getRandomTetromino(),
    id: playerId.substring(0, 4), // Use first 4 chars of socket ID as player identifier

    // 2:48pm properties new
    fallSpeed: 45,
    fallTimer: 0,
    softDropSpeed: 5,

    // 3:08pm new
    dasDirection: null, // 'left', 'right', or null
    dasTimer: 0,
    dasRepeatTimer: 0,

    // 3:18pm new
    lockTimer : 0,
    isLocking: false
  };
  
  // Return updated game state
  return gameState;
}

function handleDisconnect(gameState, playerId) {
  // Remove the disconnected player from the game state
  delete gameState.players[playerId];
  return gameState;
}

// Check if a move is valid (no collision with walls or other pieces)
function isValidMove(board, tetromino, x, y) {
  const shape = tetromino.shape;
  for (let r = 0; r < shape.length; r++) {
    for (let c = 0; c < shape[r].length; c++) {
      if (shape[r][c] !== 0) {
        const boardX = x + c;
        const boardY = y + r;
        
        // Check boundaries
        if (boardX < 0 || boardX >= board[0].length || boardY >= board.length) {
          return false;
        }
        
        // Check if there's already a piece on the board
        if (boardY >= 0 && board[boardY][boardX] !== 0) {
          return false;
        }
      }
    }
  }
  return true;
}

// Place a tetromino on the board
function placeTetromino(board, tetromino, x, y, playerId) {
  const shape = tetromino.shape;
  // Create a copy of the board so we don't modify the original
  const newBoard = board.map(row => [...row]);
  
  for (let r = 0; r < shape.length; r++) {
    for (let c = 0; c < shape[r].length; c++) {
      if (shape[r][c] !== 0 && y + r >= 0) {
        newBoard[y + r][x + c] = {
          value: shape[r][c],
          playerId: playerId
        };
      }
    }
  }
  return newBoard;
}

// Rotate a tetromino (90 degrees clockwise)
function rotateTetromino(tetromino) {
  const newShape = [];
  for (let c = 0; c < tetromino.shape[0].length; c++) {
    const newRow = [];
    for (let r = tetromino.shape.length - 1; r >= 0; r--) {
      newRow.push(tetromino.shape[r][c]);
    }
    newShape.push(newRow);
  }
  
  return {
    ...tetromino,
    shape: newShape
  };
}

// Check for completed lines and clear them
function clearLines(gameState) {
  const board = gameState.board;
  let linesToClear = [];
  
  // Find full rows
  for (let r = 0; r < board.length; r++) {
    if (board[r].every(cell => cell !== 0)) {
      linesToClear.push(r);
    }
  }
  
  if (linesToClear.length > 0) {
    // Set up for line clear animation
    gameState.lineClearActive = true;
    gameState.lineClearTimer = 0;
    gameState.linesToClear = linesToClear;
    
    return {
      newBoard: board, // Return unchanged during animation
      linesCleared: linesToClear.length
    };
  }
  
  // No lines to clear, return as before
  return { newBoard: board, linesCleared: 0 };
}

function handlePlayerAction(gameState, playerId, action) {
  const player = gameState.players[playerId];
  if (!player) return gameState; // Safety check, player might not exist
  
  let { x, y } = player;
  let { currentPiece } = player;
  const board = gameState.board;
  let successfulMove = false; // Track if move was successful
  
  switch (action.type) {
    case 'moveLeft':
      if (isValidMove(board, currentPiece, x - 1, y)) {
        player.x -= 1;
        successfulMove = true;
      }
      break;
      
    case 'moveRight':
      if (isValidMove(board, currentPiece, x + 1, y)) {
        player.x += 1;
        successfulMove = true;
      }
      break;
      
    case 'rotate':
      const rotatedPiece = rotateTetromino(currentPiece);
      if (isValidMove(board, rotatedPiece, x, y)) {
        player.currentPiece = rotatedPiece;
        successfulMove = true;
      }
      break;
    
    case 'drop':
      // Move down until collision
      let newY = y;
      while (isValidMove(board, currentPiece, x, newY + 1)) {
        newY++;
      }
      
      // Place the piece on the board
      gameState.board = placeTetromino(board, currentPiece, x, newY, playerId);
      
      // Clear any completed lines
      const { newBoard, linesCleared } = clearLines(gameState);
      gameState.board = newBoard;
      player.score += linesCleared * 100;
      
      // Use entry delay for next piece (just like hardDrop)
      player.isWaitingForNextPiece = true;
      player.entryDelayTimer = 0;
      break;
    
    case 'hardDrop':
      // Move down until collision
      let hardDropY = y;
      while (isValidMove(board, currentPiece, x, hardDropY + 1)) {
        hardDropY++;
        // Award more points for hard drop (optional)
        player.score += 2;
      }
      
      // Place the piece on the board
      gameState.board = placeTetromino(board, currentPiece, x, hardDropY, playerId);
      
      // Clear any completed lines
      const { newBoard: updatedBoard, linesCleared: clearedLines } = clearLines(gameState);
      gameState.board = updatedBoard;
      player.score += clearedLines * 100;
      
      // Start entry delay for next piece
      player.isWaitingForNextPiece = true;
      player.entryDelayTimer = 0;
      break;
      
    case 'softDrop':
      // If valid move downward
      if (isValidMove(board, currentPiece, x, y + 1)) {
        player.y += 1;
        // Award points for soft drop (optional)
        player.score += 1;
      }
      // Set fall speed to faster rate while button is held
      player.fallSpeed = player.softDropSpeed;
      break;
    
    // Add this new case for handling key up of down arrow
    case 'endSoftDrop':
      // Reset to normal fall speed
      player.fallSpeed = 45; // normal speed
      break;

    // Server-side: Add to handlePlayerAction 3:11pm
    case 'startDAS':
      player.dasDirection = action.direction;
      player.dasTimer = 0;
      player.dasRepeatTimer = 0;
      break;
      
    case 'endDAS':
      player.dasDirection = null;
      break;
          
    default:
      console.log(`Unknown action type: ${action.type}`);
  }

  // Reset lock timer when player successfully moves/rotates during lock delay
  if (successfulMove && player.isLocking) {
    // Give the player more time by resetting lock delay
    // We'll use a max of 15 resets to prevent infinite lock delay
    const MAX_LOCK_RESETS = 15;
    
    if (!player.lockResets) {
      player.lockResets = 0;
    }
    
    if (player.lockResets < MAX_LOCK_RESETS) {
      player.lockTimer = 0;
      player.lockResets++;
    }
  }
  
  // Return the updated game state
  return gameState;
}

module.exports = {
  createGameState,
  handleNewPlayer,
  handleDisconnect,
  handlePlayerAction,
  TETROMINOES,
  getRandomTetromino,
  isValidMove,
  placeTetromino, 
  rotateTetromino,
  clearLines
};