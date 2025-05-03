// server/src/gameState.js

// Define tetromino shapes and colors with all rotations
const TETROMINOES = {
  // I (cyan)
  I: {
    color: 'cyan',
    rotations: [
      // 0°
      [
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      // 90°
      [
        [0, 0, 1, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 0]
      ],
      // 180°
      [
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 0, 0]
      ],
      // 270°
      [
        [0, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 1, 0, 0]
      ]
    ]
  },

  // O (yellow)
  O: {
    color: 'yellow',
    rotations: [
      // All orientations are the same
      [
        [0, 4, 4, 0],
        [0, 4, 4, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      [
        [0, 4, 4, 0],
        [0, 4, 4, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      [
        [0, 4, 4, 0],
        [0, 4, 4, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      [
        [0, 4, 4, 0],
        [0, 4, 4, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ]
    ]
  },

  // J (blue)
  J: {
    color: 'blue',
    rotations: [
      // 0°
      [
        [3, 0, 0, 0],
        [3, 3, 3, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      // 90°
      [
        [0, 3, 3, 0],
        [0, 3, 0, 0],
        [0, 3, 0, 0],
        [0, 0, 0, 0]
      ],
      // 180°
      [
        [0, 0, 0, 0],
        [3, 3, 3, 0],
        [0, 0, 3, 0],
        [0, 0, 0, 0]
      ],
      // 270°
      [
        [0, 3, 0, 0],
        [0, 3, 0, 0],
        [3, 3, 0, 0],
        [0, 0, 0, 0]
      ]
    ]
  },

  // L (orange)
  L: {
    color: 'orange',
    rotations: [
      // 0°
      [
        [0, 0, 2, 0],
        [2, 2, 2, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      // 90°
      [
        [0, 2, 0, 0],
        [0, 2, 0, 0],
        [0, 2, 2, 0],
        [0, 0, 0, 0]
      ],
      // 180°
      [
        [0, 0, 0, 0],
        [2, 2, 2, 0],
        [2, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      // 270°
      [
        [2, 2, 0, 0],
        [0, 2, 0, 0],
        [0, 2, 0, 0],
        [0, 0, 0, 0]
      ]
    ]
  },

  // S (green)
  S: {
    color: 'green',
    rotations: [
      // 0°
      [
        [0, 5, 5, 0],
        [5, 5, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      // 90°
      [
        [0, 5, 0, 0],
        [0, 5, 5, 0],
        [0, 0, 5, 0],
        [0, 0, 0, 0]
      ],
      // 180°
      [
        [0, 0, 0, 0],
        [0, 5, 5, 0],
        [5, 5, 0, 0],
        [0, 0, 0, 0]
      ],
      // 270°
      [
        [5, 0, 0, 0],
        [5, 5, 0, 0],
        [0, 5, 0, 0],
        [0, 0, 0, 0]
      ]
    ]
  },

  // Z (red)
  Z: {
    color: 'red',
    rotations: [
      // 0°
      [
        [6, 6, 0, 0],
        [0, 6, 6, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      // 90°
      [
        [0, 0, 6, 0],
        [0, 6, 6, 0],
        [0, 6, 0, 0],
        [0, 0, 0, 0]
      ],
      // 180°
      [
        [0, 0, 0, 0],
        [6, 6, 0, 0],
        [0, 6, 6, 0],
        [0, 0, 0, 0]
      ],
      // 270°
      [
        [0, 6, 0, 0],
        [6, 6, 0, 0],
        [6, 0, 0, 0],
        [0, 0, 0, 0]
      ]
    ]
  },

  // T (purple)
  T: {
    color: 'purple',
    rotations: [
      // 0°
      [
        [0, 7, 0, 0],
        [7, 7, 7, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ],
      // 90°
      [
        [0, 7, 0, 0],
        [0, 7, 7, 0],
        [0, 7, 0, 0],
        [0, 0, 0, 0]
      ],
      // 180°
      [
        [0, 0, 0, 0],
        [7, 7, 7, 0],
        [0, 7, 0, 0],
        [0, 0, 0, 0]
      ],
      // 270°
      [
        [0, 7, 0, 0],
        [7, 7, 0, 0],
        [0, 7, 0, 0],
        [0, 0, 0, 0]
      ]
    ]
  }
};

// Get a random tetromino type
function getRandomTetromino() {
  const types = Object.keys(TETROMINOES);
  const randomType = types[Math.floor(Math.random() * types.length)];
  const tetromino = TETROMINOES[randomType];
  
  return { 
    type: randomType,
    color: tetromino.color,
    shape: tetromino.rotations[0], // Use first rotation as default
    rotationIndex: 0 // Track current rotation
  };
}

function getBoardDimensions(playerCount) {
  switch (playerCount) {
    case 1: return { rows: 20, cols: 10 }; // Standard single player
    case 2: return { rows: 20, cols: 14 }; // Two players
    case 3: return { rows: 20, cols: 21 }; // Three players
    case 4: return { rows: 20, cols: 28 }; // Four players
    default: return { rows: 20, cols: 10 }; // Default
  }
}

function createGameState() {
  return {
    appPhase: 'homescreen',
    board: createEmptyBoard(20, 10),
    players: {}, // All active players
    activePlayers: new Set(), // Track which players are currently active
    disconnectedPlayers: {}, // Store data for disconnected players who might rejoin
    playerColors: ['#FF5733', '#33FF57', '#3357FF', '#F3FF33'],
    lineClearActive: false,
    lineClearTimer: 0,
    linesToClear: [],
    gameMode: 'classic',
    readyPlayers: [],
    gameInProgress: false
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
  // If game is in progress, don't add new players
  if (gameState.appPhase === 'playing') {
    console.log(`Player ${playerId} tried to join during active game`);
    return gameState;
  }
  
  // Ensure activePlayers is a Set
  if (!(gameState.activePlayers instanceof Set)) {
    gameState.activePlayers = new Set(Array.isArray(gameState.activePlayers) 
      ? gameState.activePlayers 
      : Object.keys(gameState.activePlayers || {}));
  }
  
  // Check for potential rejoin
  const shortId = playerId.substring(0, 4);
  
  // First, clean up any existing instances of this player (prevent ghost instances)
  for (const existingId in gameState.players) {
    const existingPlayer = gameState.players[existingId];
    if (existingPlayer && existingPlayer.id === shortId) {
      console.log(`Found existing player instance with id ${shortId}, cleaning up before reconnection`);
      
      // Clean up player's blocks from the board
      if (gameState.board) {
        gameState.board = gameState.board.map(row => 
          row.map(cell => {
            if (cell !== 0 && typeof cell === 'object' && cell.playerId === existingId) {
              return 0;
            }
            return cell;
          })
        );
      }
      
      // Remove the existing player
      delete gameState.players[existingId];
      gameState.activePlayers.delete(existingId);
      
      // Remove from ready players if present
      gameState.readyPlayers = gameState.readyPlayers.filter(id => id !== existingId);
      
      break;  // We only need to remove one instance
    }
  }
  
  if (gameState.disconnectedPlayers && gameState.disconnectedPlayers[shortId]) {
    console.log(`Player ${shortId} is rejoining`);
    const savedData = gameState.disconnectedPlayers[shortId];
    
    // Create player with saved data
    gameState.players[playerId] = {
      id: shortId,
      playerNumber: savedData.playerNumber,
      color: savedData.color,
      score: 0,
      isReady: false,
      isRejoining: true,
      x: 4, y: 0,
      currentPiece: getRandomTetromino(),
      fallSpeed: 45, fallTimer: 0,
      softDropSpeed: 5,
      dasDirection: null, dasTimer: 0, dasRepeatTimer: 0,
      lockTimer: 0, isLocking: false,
      entryDelayTimer: 0, isWaitingForNextPiece: false,
      lockResets: 0,
      justPerformedHardDrop: false, // Add this flag for hard drop control
      isSoftDropping: false // Add this flag for soft drop control: hold down to soft drop
    };
    
    gameState.activePlayers.add(playerId);
    delete gameState.disconnectedPlayers[shortId];
    return gameState;
  }
  
  // Find next available player number
  let playerNumber = 1;
  const usedNumbers = new Set(Object.values(gameState.players).map(p => p.playerNumber));
  while (usedNumbers.has(playerNumber)) playerNumber++;
  
  // Determine color based on player count
  const colorIndex = Object.keys(gameState.players).length % gameState.playerColors.length;
  
  // Create new player
  gameState.players[playerId] = {
    id: playerId.substring(0, 4),
    playerNumber: playerNumber,
    isReady: false,
    color: gameState.playerColors[colorIndex],
    score: 0,
    x: 4, y: 0,
    currentPiece: getRandomTetromino(),
    fallSpeed: 45, fallTimer: 0,
    softDropSpeed: 5,
    dasDirection: null, dasTimer: 0, dasRepeatTimer: 0,
    lockTimer: 0, isLocking: false,
    entryDelayTimer: 0, isWaitingForNextPiece: false,
    lockResets: 0,
    justPerformedHardDrop: false // Add this flag for hard drop control
  };
  
  gameState.activePlayers.add(playerId);
  return gameState;
}

function handleDisconnect(gameState, playerId) {
  // Remove from active players
  gameState.activePlayers.delete(playerId);
  const player = gameState.players[playerId];
  
  if (player) {
    // Remove from ready players
    gameState.readyPlayers = gameState.readyPlayers.filter(id => id !== playerId);
    
    // If game in progress, save player data for potential rejoin
    if (gameState.appPhase === 'playing') {
      // Save player data for potential rejoin
      gameState.disconnectedPlayers[player.id] = {
        playerNumber: player.playerNumber,
        color: player.color,
        score: player.score,
        originalId: playerId,
        disconnectedAt: Date.now()
      };
      
      // Remove current piece
      if (player.currentPiece) {
        player.currentPiece = null;
        console.log(`Removed piece for disconnected player ${playerId}`);
      }
      
      // Clean up player blocks from the board
      // We need to create a new board without this player's blocks
      if (gameState.board) {
        const newBoard = gameState.board.map(row => 
          row.map(cell => {
            // If this is a cell owned by the disconnected player, clear it
            if (cell !== 0 && typeof cell === 'object' && cell.playerId === playerId) {
              return 0;
            }
            return cell;
          })
        );
        gameState.board = newBoard;
        console.log(`Cleaned up board from disconnected player ${playerId}`);
      }
      
      // Remove player from active game
      delete gameState.players[playerId];
      
      // Check if all players have disconnected
      if (gameState.activePlayers.size === 0) {
        // End the game
        gameState.appPhase = 'homescreen';
        gameState.gameInProgress = false;
        gameState.disconnectedPlayers = {};
        console.log('All players disconnected, ending game');
      }
    } else {
      // Just remove the player if not in a game
      delete gameState.players[playerId];
    }
  }
  
  return gameState;
}

function isValidMoveOnBoard(board, tetromino, x, y) {
  if (!tetromino || !tetromino.shape) return false;
  
  for (let r = 0; r < tetromino.shape.length; r++) {
    for (let c = 0; c < tetromino.shape[r].length; c++) {
      if (tetromino.shape[r][c] !== 0) {
        const boardX = x + c, boardY = y + r;
        
        // Check boundaries and collisions with locked pieces
        if (boardX < 0 || boardX >= board[0].length || boardY >= board.length) return false;
        if (boardY >= 0 && board[boardY][boardX] !== 0) return false;
      }
    }
  }
  return true;
}

function isValidMove(board, tetromino, x, y, currentPlayerId, allPlayers) {
  // Safety check for tetromino
  if (!tetromino || !tetromino.shape) return false;
  
  // First check board boundaries and locked pieces
  if (!isValidMoveOnBoard(board, tetromino, x, y)) return false;
  
  // Then check for collisions with other players' active pieces
  for (let r = 0; r < tetromino.shape.length; r++) {
    for (let c = 0; c < tetromino.shape[r].length; c++) {
      if (tetromino.shape[r][c] !== 0) {
        const boardX = x + c, boardY = y + r;
        
        // Skip if this cell is above the board
        if (boardY < 0) continue;
        
        // Check each player's active piece
        for (const playerId in allPlayers) {
          const otherPlayer = allPlayers[playerId];
          
          // Skip current player and players without pieces
          if (playerId === currentPlayerId || !otherPlayer.currentPiece || 
              otherPlayer.isWaitingForNextPiece) continue;
          
          // Check collision with other player's piece
          for (let pr = 0; pr < otherPlayer.currentPiece.shape.length; pr++) {
            for (let pc = 0; pc < otherPlayer.currentPiece.shape[pr].length; pc++) {
              if (otherPlayer.currentPiece.shape[pr][pc] !== 0) {
                const otherX = otherPlayer.x + pc, otherY = otherPlayer.y + pr;
                
                // If positions match, we have a collision
                if (boardX === otherX && boardY === otherY) return false;
              }
            }
          }
        }
      }
    }
  }
  return true;
}

function placeTetromino(board, tetromino, x, y, playerId) {
  if (!tetromino || !tetromino.shape) return board;
  
  const newBoard = board.map(row => [...row]);
  for (let r = 0; r < tetromino.shape.length; r++) {
    for (let c = 0; c < tetromino.shape[r].length; c++) {
      if (tetromino.shape[r][c] !== 0 && y + r >= 0) {
        newBoard[y + r][x + c] = { value: tetromino.shape[r][c], playerId };
      }
    }
  }
  return newBoard;
}

function rotateTetromino(tetromino) {
  const { type, rotationIndex } = tetromino;
  const tetrominoData = TETROMINOES[type];
  
  if (!tetrominoData || !tetrominoData.rotations) {
    console.error(`Invalid tetromino type: ${type}`);
    return tetromino;
  }
  
  // Calculate next rotation index (0 -> 1 -> 2 -> 3 -> 0)
  const nextRotationIndex = (rotationIndex + 1) % tetrominoData.rotations.length;
  
  // Return a new tetromino object with the rotated shape
  return {
    ...tetromino,
    shape: tetrominoData.rotations[nextRotationIndex],
    rotationIndex: nextRotationIndex
  };
}

function clearLines(gameState) {
  const board = gameState.board;
  const linesToClear = [];
  
  // Find completed lines
  for (let row = 0; row < board.length; row++) {
    if (board[row].every(cell => cell !== 0)) linesToClear.push(row);
  }
  
  // Start clear animation
  if (linesToClear.length > 0) {
    gameState.lineClearActive = true;
    gameState.lineClearTimer = 0;
    gameState.linesToClear = linesToClear;
  }
  
  return { newBoard: board, linesCleared: linesToClear.length };
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

function handlePlayerAction(gameState, playerId, action) {
  const player = gameState.players[playerId];
  if (!player || !player.currentPiece) return gameState;
  
  let { x, y } = player;
  let { currentPiece } = player;
  const board = gameState.board;
  let successfulMove = false;
  
  // Check if action is a hard drop and player just performed one
  if (action.type === 'hardDrop' && player.justPerformedHardDrop) {
    // Ignore this action - we don't allow rapid hard drops
    return gameState;
  }
  
  switch (action.type) {
    case 'moveLeft':
      if (isValidMove(board, currentPiece, x - 1, y, playerId, gameState.players)) {
        player.x -= 1;
        successfulMove = true;
      }
      break;
      
    case 'moveRight':
      if (isValidMove(board, currentPiece, x + 1, y, playerId, gameState.players)) {
        player.x += 1;
        successfulMove = true;
      }
      break;
      
    case 'rotate':
      const rotatedPiece = rotateTetromino(currentPiece);
      if (isValidMove(board, rotatedPiece, x, y, playerId, gameState.players)) {
        player.currentPiece = rotatedPiece;
        successfulMove = true;
      }
      break;
    
    case 'drop':
      // Move down until collision
      let newY = y;
      while (isValidMove(board, currentPiece, x, newY + 1, playerId, gameState.players)) newY++;
      
      // Place the piece and clear lines
      gameState.board = placeTetromino(board, currentPiece, x, newY, playerId);
      const { newBoard, linesCleared } = clearLines(gameState);
      gameState.board = newBoard;
      player.score += linesCleared * 100;
      
      // Prepare for next piece
      player.isWaitingForNextPiece = true;
      player.entryDelayTimer = 0;
      break;
    
      case 'hardDrop': {
        /* ── slide downward until the very last *valid* row ──────────── */
        let targetY = y;
        while (
          isValidMove(board, currentPiece, x, targetY + 1, playerId, gameState.players)
        ) {
          targetY++;
          player.score += 2;                        // +2 pts per cell (Guideline)
        }
      
        /* ── can we lock here (floor or locked block beneath)? ───────── */
        const canLockHere = isTouchingGround(board, currentPiece, x, targetY);
      
        if (canLockHere) {
          /* normal hard-drop → instant lock */
          gameState.board = placeTetromino(board, currentPiece, x, targetY, playerId);
          const { newBoard, linesCleared } = clearLines(gameState);
          gameState.board = newBoard;
          player.score += linesCleared * 100;
      
          player.isWaitingForNextPiece = true;
          player.entryDelayTimer       = 0;
          player.justPerformedHardDrop = true;      // block turbo-tapping
        } else {
          /* bumped another *active* piece → rest above it, stay active  */
          player.y = targetY;
          player.justPerformedHardDrop = false;     // allow another hard-drop later
        }
        break;
      }
      
    case 'softDrop':
      if (isValidMove(board, currentPiece, x, y + 1, playerId, gameState.players)) {
        player.y += 1;
        player.score += 1; // Award points for soft drop
      }
      player.fallSpeed = player.softDropSpeed;
      player.isSoftDropping = true; // Set soft drop flag
      break;
    
    case 'endSoftDrop':
      player.fallSpeed = 45; // Reset to normal fall speed
      player.isSoftDropping = false; // Reset soft drop flag
      break;

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

  // Reset lock timer on successful move during lock delay
  if (successfulMove && player.isLocking) {
    const MAX_LOCK_RESETS = 15;
    if (!player.lockResets) player.lockResets = 0;
    
    if (player.lockResets < MAX_LOCK_RESETS) {
      player.lockTimer = 0;
      player.lockResets++;
    }
  }
  
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
  isValidMoveOnBoard,
  placeTetromino, 
  rotateTetromino,
  clearLines,
  createEmptyBoard,
  getBoardDimensions,
  isTouchingGround
};