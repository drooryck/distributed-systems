import React, { useEffect, useRef } from 'react';

// Map of tetromino values to colors
const COLORS = {
  1: 'cyan',    // I
  2: 'blue',    // J
  3: 'orange',  // L
  4: 'yellow',  // O
  5: 'green',   // S
  6: 'purple',  // T
  7: 'red'      // Z
};

function GameBoard({ board, players, currentPlayerId }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw a dark background
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw the grid
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    
    const cellSize = 30; // each cell is 30px
    
    // Draw grid lines
    for (let r = 0; r <= board.length; r++) {
      ctx.beginPath();
      ctx.moveTo(0, r * cellSize);
      ctx.lineTo(canvas.width, r * cellSize);
      ctx.stroke();
    }
    
    for (let c = 0; c <= board[0].length; c++) {
      ctx.beginPath();
      ctx.moveTo(c * cellSize, 0);
      ctx.lineTo(c * cellSize, canvas.height);
      ctx.stroke();
    }
    
    // Draw placed pieces on the board
    for (let r = 0; r < board.length; r++) {
      for (let c = 0; c < board[r].length; c++) {
        const cell = board[r][c];
        if (cell !== 0) {
          // If the cell has a complex structure (from server)
          if (typeof cell === 'object') {
            const playerId = cell.playerId;
            const player = Object.values(players).find(p => p.id === playerId.substring(0, 4));
            ctx.fillStyle = player ? player.color : 'gray';
          } else {
            // If it's just a number (simple case)
            ctx.fillStyle = COLORS[cell] || 'gray';
          }
          
          ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize);
          ctx.strokeStyle = '#FFF';
          ctx.lineWidth = 1;
          ctx.strokeRect(c * cellSize, r * cellSize, cellSize, cellSize);
        }
      }
    }

  // Draw line clear animation if active
  if (board && Array.isArray(board.linesToClear) && board.linesToClear.length > 0) {
    board.linesToClear.forEach(rowIndex => {
      // Flash or highlight the rows being cleared
      const flash = Math.floor(Date.now() / 100) % 2 === 0;
      ctx.fillStyle = flash ? '#FFFFFF' : '#888888';
      
      ctx.fillRect(0, rowIndex * cellSize, canvas.width, cellSize);
    });
  }
      
    // Draw active tetromino for each player
    Object.values(players).forEach(player => {
      const { x, y, currentPiece, color } = player;
      
      if (!currentPiece) return;
      
      const shape = currentPiece.shape;
      
      for (let r = 0; r < shape.length; r++) {
        for (let c = 0; c < shape[r].length; c++) {
          if (shape[r][c] !== 0) {
            const boardX = x + c;
            const boardY = y + r;
            
            // Skip if out of bounds or above the board
            if (boardX < 0 || boardX >= board[0].length || 
                boardY < 0 || boardY >= board.length) {
              continue;
            }
            
            ctx.fillStyle = color || currentPiece.color || 'gray';
            ctx.fillRect(boardX * cellSize, boardY * cellSize, cellSize, cellSize);
            ctx.strokeStyle = '#FFF';
            ctx.lineWidth = 1;
            ctx.strokeRect(boardX * cellSize, boardY * cellSize, cellSize, cellSize);
          }
        }
      }
    });
    
  }, [board, players, currentPlayerId]);

  return (
    <div>
      <canvas
        ref={canvasRef}
        width={300}  // 10 columns * 30 px
        height={600} // 20 rows * 30 px
        style={{ border: '2px solid #555' }}
      />
    </div>
  );
}

export default GameBoard;