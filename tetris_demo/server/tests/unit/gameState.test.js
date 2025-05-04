const { 
  createGameState, 
  getRandomTetromino,
  isValidMove,
  isValidMoveOnBoard,
  placeTetromino,
  rotateTetromino,
  clearLines,
  createEmptyBoard,
  getBoardDimensions,
  isTouchingGround,
  handleNewPlayer,
  handleDisconnect,
  handlePlayerAction,
  TETROMINOES
} = require('../../src/gameState');

describe('Game State Functions', () => {
  describe('createGameState', () => {
    test('initializes with correct default values', () => {
      const state = createGameState();
      expect(state.appPhase).toBe('homescreen');
      expect(state.players).toEqual({});
      expect(state.activePlayers instanceof Set).toBe(true);
      expect(state.activePlayers.size).toBe(0);
      expect(Array.isArray(state.board)).toBe(true);
      expect(state.board.length).toBe(20);
      expect(state.board[0].length).toBe(10);
    });
  });
  
  describe('getBoardDimensions', () => {
    test('returns correct dimensions based on player count', () => {
      expect(getBoardDimensions(1)).toEqual({ rows: 20, cols: 10 });
      expect(getBoardDimensions(2)).toEqual({ rows: 20, cols: 14 });
      expect(getBoardDimensions(3)).toEqual({ rows: 20, cols: 21 });
      expect(getBoardDimensions(4)).toEqual({ rows: 20, cols: 28 });
      expect(getBoardDimensions(5)).toEqual({ rows: 20, cols: 10 }); // Default case
    });
  });

  describe('createEmptyBoard', () => {
    test('creates a board with specified dimensions', () => {
      const board = createEmptyBoard(15, 8);
      expect(board.length).toBe(15);
      expect(board[0].length).toBe(8);
      expect(board.every(row => row.every(cell => cell === 0))).toBe(true);
    });
  });
  
  describe('getRandomTetromino', () => {
    test('returns a valid tetromino with shape and color', () => {
      const tetromino = getRandomTetromino();
      expect(tetromino).toHaveProperty('type');
      expect(tetromino).toHaveProperty('shape');
      expect(tetromino).toHaveProperty('color');
      expect(tetromino).toHaveProperty('rotationIndex');
      expect(tetromino.rotationIndex).toBe(0);
      
      // Validate that type exists in TETROMINOES
      expect(Object.keys(TETROMINOES)).toContain(tetromino.type);
    });
  });
  
  describe('isValidMoveOnBoard', () => {
    test('allows valid moves within board boundaries', () => {
      const board = createEmptyBoard(20, 10);
      const tetromino = {
        shape: [
          [1, 1, 0, 0],
          [1, 1, 0, 0],
          [0, 0, 0, 0],
          [0, 0, 0, 0]
        ]
      };
      
      expect(isValidMoveOnBoard(board, tetromino, 0, 0)).toBe(true);
      expect(isValidMoveOnBoard(board, tetromino, 8, 0)).toBe(true);
      expect(isValidMoveOnBoard(board, tetromino, 9, 0)).toBe(false); // Out of bounds
    });
    
    test('detects collisions with locked pieces', () => {
      const board = createEmptyBoard(20, 10);
      board[19][0] = { value: 1, playerId: 'oldPiece' }; // Placed block
      
      const tetromino = {
        shape: [
          [1, 1, 0, 0],
          [1, 1, 0, 0],
          [0, 0, 0, 0],
          [0, 0, 0, 0]
        ]
      };
      
      expect(isValidMoveOnBoard(board, tetromino, 0, 17)).toBe(true);
      expect(isValidMoveOnBoard(board, tetromino, 0, 18)).toBe(false); // Collision
    });
  });

  describe('isValidMove', () => {
    test('checks for collisions with other players active pieces', () => {
      const board = createEmptyBoard(20, 10);
      const players = {
        'player1': {
          currentPiece: {
            shape: [
              [1, 1, 0, 0],
              [1, 1, 0, 0],
              [0, 0, 0, 0],
              [0, 0, 0, 0]
            ]
          },
          x: 4,
          y: 10
        },
        'player2': {
          currentPiece: {
            shape: [
              [2, 2, 0, 0],
              [0, 2, 2, 0],
              [0, 0, 0, 0],
              [0, 0, 0, 0]
            ]
          },
          x: 4,
          y: 8
        }
      };

      // Player1 trying to move up into player2's position
      expect(isValidMove(board, players.player1.currentPiece, 4, 9, 'player1', players)).toBe(false);
      
      // Player1 can move to the side
      expect(isValidMove(board, players.player1.currentPiece, 6, 10, 'player1', players)).toBe(true);
    });
  });
  
  describe('placeTetromino', () => {
    test('places tetromino on the board', () => {
      const board = createEmptyBoard(20, 10);
      const tetromino = {
        shape: [
          [1, 1, 0, 0],
          [1, 1, 0, 0],
          [0, 0, 0, 0],
          [0, 0, 0, 0]
        ]
      };
      
      const newBoard = placeTetromino(board, tetromino, 0, 0, 'player1');
      
      expect(newBoard[0][0]).toEqual({ value: 1, playerId: 'player1' });
      expect(newBoard[0][1]).toEqual({ value: 1, playerId: 'player1' });
      expect(newBoard[1][0]).toEqual({ value: 1, playerId: 'player1' });
      expect(newBoard[1][1]).toEqual({ value: 1, playerId: 'player1' });
      expect(newBoard[2][0]).toBe(0); // Should remain empty
    });
  });
  
  describe('rotateTetromino', () => {
    test('rotates I tetromino clockwise', () => {
      const tetromino = {
        type: 'I',
        shape: TETROMINOES.I.rotations[0],
        rotationIndex: 0
      };
      
      const rotated = rotateTetromino(tetromino);
      
      expect(rotated.rotationIndex).toBe(1);
      expect(rotated.shape).toEqual(TETROMINOES.I.rotations[1]);
    });
    
    test('rotates O tetromino (should remain same shape)', () => {
      const tetromino = {
        type: 'O',
        shape: TETROMINOES.O.rotations[0],
        rotationIndex: 0
      };
      
      const rotated = rotateTetromino(tetromino);
      
      expect(rotated.rotationIndex).toBe(1);
      // O tetromino shape should remain the same regardless of rotation
      expect(rotated.shape).toEqual(tetromino.shape);
    });
  });
  
  describe('isTouchingGround', () => {
    test('detects when piece is at board bottom', () => {
      const board = createEmptyBoard(20, 10);
      const tetromino = {
        shape: [
          [1, 1, 0, 0],
          [1, 1, 0, 0],
          [0, 0, 0, 0],
          [0, 0, 0, 0]
        ]
      };
      
      expect(isTouchingGround(board, tetromino, 0, 18)).toBe(true); // At board bottom
      expect(isTouchingGround(board, tetromino, 0, 17)).toBe(false); // One space above bottom
    });
    
    test('detects when piece is above another piece', () => {
      const board = createEmptyBoard(20, 10);
      board[15][0] = { value: 1, playerId: 'oldPiece' }; // Placed block
      
      const tetromino = {
        shape: [
          [1, 1, 0, 0],
          [1, 1, 0, 0],
          [0, 0, 0, 0],
          [0, 0, 0, 0]
        ]
      };
      
      expect(isTouchingGround(board, tetromino, 0, 13)).toBe(true); // Will touch the piece below
      expect(isTouchingGround(board, tetromino, 0, 12)).toBe(false); // One space above
    });
  });

  describe('clearLines', () => {
    test('identifies completed lines', () => {
      const gameState = createGameState();
      // Create a board with one complete line
      for (let c = 0; c < 10; c++) {
        gameState.board[18][c] = { value: 1, playerId: 'player1' };
      }
      
      const result = clearLines(gameState);
      
      expect(gameState.linesToClear).toEqual([18]);
      expect(gameState.lineClearActive).toBe(true);
      expect(result.linesCleared).toBe(1);
    });
  });

  describe('handleNewPlayer', () => {
    test('adds a new player to the game state', () => {
      const gameState = createGameState();
      const playerId = 'player1';
      
      const updatedState = handleNewPlayer(gameState, playerId);
      
      expect(updatedState.players).toHaveProperty(playerId);
      expect(updatedState.players[playerId].id).toBe(playerId.substring(0, 4));
      expect(updatedState.players[playerId].playerNumber).toBe(1);
      expect(updatedState.activePlayers.has(playerId)).toBe(true);
    });
    
    test('does not add player if game is in playing phase', () => {
      const gameState = createGameState();
      gameState.appPhase = 'playing';
      const playerId = 'player1';
      
      const updatedState = handleNewPlayer(gameState, playerId);
      
      expect(updatedState.players).not.toHaveProperty(playerId);
    });
  });

  describe('handleDisconnect', () => {
    test('removes player from active players', () => {
      const gameState = createGameState();
      const playerId = 'player1';
      
      // Add player first
      handleNewPlayer(gameState, playerId);
      expect(gameState.activePlayers.has(playerId)).toBe(true);
      
      // Disconnect player
      handleDisconnect(gameState, playerId);
      
      expect(gameState.activePlayers.has(playerId)).toBe(false);
      expect(gameState.players).not.toHaveProperty(playerId);
    });
    
    test('saves player data for rejoining during gameplay', () => {
      const gameState = createGameState();
      const playerId = 'player1';
      
      // Add player first
      handleNewPlayer(gameState, playerId);
      gameState.appPhase = 'playing';
      const shortId = playerId.substring(0, 4);
      
      // Disconnect player during gameplay
      handleDisconnect(gameState, playerId);
      
      expect(gameState.disconnectedPlayers).toHaveProperty(shortId);
      expect(gameState.disconnectedPlayers[shortId].playerNumber).toBe(1);
    });
  });

  describe('handlePlayerAction', () => {
    test('moves tetromino left', () => {
      const gameState = createGameState();
      const playerId = 'player1';
      
      // Add player and set initial position
      handleNewPlayer(gameState, playerId);
      gameState.players[playerId].x = 5;
      
      // Move left
      handlePlayerAction(gameState, playerId, { type: 'moveLeft' });
      
      expect(gameState.players[playerId].x).toBe(4);
    });
    
    test('rotates tetromino', () => {
      const gameState = createGameState();
      const playerId = 'player1';
      
      // Add player
      handleNewPlayer(gameState, playerId);
      const initialRotationIndex = gameState.players[playerId].currentPiece.rotationIndex;
      
      // Rotate piece
      handlePlayerAction(gameState, playerId, { type: 'rotate' });
      
      expect(gameState.players[playerId].currentPiece.rotationIndex).toBe(
        (initialRotationIndex + 1) % 4
      );
    });
    
    test('performs soft drop', () => {
      const gameState = createGameState();
      const playerId = 'player1';
      
      // Add player and set initial position
      handleNewPlayer(gameState, playerId);
      gameState.players[playerId].y = 5;
      const initialScore = gameState.players[playerId].score;
      
      // Soft drop
      handlePlayerAction(gameState, playerId, { type: 'softDrop' });
      
      expect(gameState.players[playerId].y).toBe(6);
      expect(gameState.players[playerId].score).toBe(initialScore + 1); // +1 for soft drop
      expect(gameState.players[playerId].isSoftDropping).toBe(true);
    });
    
    test('performs hard drop', () => {
      const gameState = createGameState();
      const playerId = 'player1';
      
      // Add player and set initial position
      handleNewPlayer(gameState, playerId);
      gameState.players[playerId].y = 5;
      
      // Hard drop
      handlePlayerAction(gameState, playerId, { type: 'hardDrop' });
      
      // Player should be in waiting state after hard drop
      expect(gameState.players[playerId].isWaitingForNextPiece).toBe(true);
      expect(gameState.players[playerId].justPerformedHardDrop).toBe(true);
    });
  });
});