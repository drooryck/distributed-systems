import React, { useEffect, useRef } from 'react';

// Map of tetromino values to colors (TGM2-inspired color scheme)
const COLORS = {
  1: { // I - Cyan
    main: '#00FFFF',
    light: '#AAFFFF',
    dark: '#009999'
  },
  2: { // J - Blue
    main: '#0000FF',
    light: '#9999FF',
    dark: '#000099'
  },
  3: { // L - Orange
    main: '#FF7700',
    light: '#FFBB77',
    dark: '#994700'
  },
  4: { // O - Yellow
    main: '#FFFF00',
    light: '#FFFFAA',
    dark: '#999900'
  },
  5: { // S - Green
    main: '#00FF00', 
    light: '#AAFFAA',
    dark: '#009900'
  },
  6: { // T - Purple
    main: '#AA00FF',
    light: '#DDAAFF',
    dark: '#550077'
  },
  7: { // Z - Red
    main: '#FF0000',
    light: '#FFAAAA',
    dark: '#990000'
  }
};

function GameBoard({ board, players, currentPlayerId }) {
  const canvasRef = useRef(null);
  const cellSize = 30; // each cell is 30px
  
  // Calculate canvas dimensions based on board size
  const canvasWidth = board?.[0]?.length ? board[0].length * cellSize : 300;
  const canvasHeight = board?.length ? board.length * cellSize : 600;

  // Helper function to draw a TGM2-style block
  const drawTGMBlock = (ctx, x, y, color) => {
    const blockColors = typeof color === 'string' 
      ? { main: color, light: '#FFFFFF', dark: '#555555' } 
      : color;
      
    const padding = 1; // Space between blocks
    
    // Background (darker version of the main color)
    ctx.fillStyle = blockColors.dark;
    ctx.fillRect(
      x * cellSize + padding, 
      y * cellSize + padding, 
      cellSize - padding * 2, 
      cellSize - padding * 2
    );
    
    // Main color fill (slightly smaller than the full cell)
    ctx.fillStyle = blockColors.main;
    ctx.fillRect(
      x * cellSize + padding + 2, 
      y * cellSize + padding + 2, 
      cellSize - padding * 4, 
      cellSize - padding * 4
    );
    
    // Top-left edge highlight (light)
    ctx.beginPath();
    ctx.moveTo(x * cellSize + padding, y * cellSize + padding);
    ctx.lineTo(x * cellSize + cellSize - padding, y * cellSize + padding);
    ctx.lineTo(x * cellSize + cellSize - padding - 4, y * cellSize + padding + 4);
    ctx.lineTo(x * cellSize + padding + 4, y * cellSize + padding + 4);
    ctx.lineTo(x * cellSize + padding + 4, y * cellSize + cellSize - padding - 4);
    ctx.lineTo(x * cellSize + padding, y * cellSize + cellSize - padding);
    ctx.closePath();
    ctx.fillStyle = blockColors.light;
    ctx.fill();
    
    // Bottom-right edge shadow (dark)
    ctx.beginPath();
    ctx.moveTo(x * cellSize + cellSize - padding, y * cellSize + padding);
    ctx.lineTo(x * cellSize + cellSize - padding, y * cellSize + cellSize - padding);
    ctx.lineTo(x * cellSize + padding, y * cellSize + cellSize - padding);
    ctx.lineTo(x * cellSize + padding + 4, y * cellSize + cellSize - padding - 4);
    ctx.lineTo(x * cellSize + cellSize - padding - 4, y * cellSize + cellSize - padding - 4);
    ctx.lineTo(x * cellSize + cellSize - padding - 4, y * cellSize + padding + 4);
    ctx.closePath();
    ctx.fillStyle = blockColors.dark;
    ctx.fill();
    
    // Small highlight in top-left corner (classic TGM style)
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(
      x * cellSize + padding + 3, 
      y * cellSize + padding + 3, 
      3, 
      3
    );
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw a dark background
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw the grid (subtle)
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    
    // Draw grid lines
    for (let r = 0; r <= board.length; r++) {
      ctx.beginPath();
      ctx.moveTo(0, r * cellSize);
      ctx.lineTo(canvas.width, r * cellSize);
      ctx.stroke();
    }
    
    for (let c = 0; c <= (board[0]?.length || 0); c++) {
      ctx.beginPath();
      ctx.moveTo(c * cellSize, 0);
      ctx.lineTo(c * cellSize, canvas.height);
      ctx.stroke();
    }
    
    // Draw placed pieces on the board
    for (let r = 0; r < board.length; r++) {
      if (!board[r]) continue;
      
      for (let c = 0; c < board[r].length; c++) {
        const cell = board[r][c];
        if (cell !== 0) {
          // If the cell has a complex structure (from server)
          if (typeof cell === 'object' && cell !== null) {
            const playerId = cell.playerId;
            if (!playerId) {
              drawTGMBlock(ctx, c, r, { main: 'gray', light: '#AAA', dark: '#444' });
            } else {
              const player = Object.values(players || {}).find(p => p && p.id === playerId.substring(0, 4));
              const color = player ? player.color : 'gray';
              drawTGMBlock(ctx, c, r, { main: color, light: '#FFFFFF', dark: '#555555' });
            }
          } else {
            // If it's just a number (simple case)
            drawTGMBlock(ctx, c, r, COLORS[cell] || { main: 'gray', light: '#AAA', dark: '#444' });
          }
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
    if (players && typeof players === 'object') {
      Object.values(players).forEach(player => {
        if (!player || !player.currentPiece || !player.currentPiece.shape) return;
        
        const { x, y, currentPiece, color } = player;
        const shape = currentPiece.shape;
        
        if (!Array.isArray(shape)) return;
        
        for (let r = 0; r < shape.length; r++) {
          if (!Array.isArray(shape[r])) continue;
          
          for (let c = 0; c < shape[r].length; c++) {
            if (shape[r][c] !== 0) {
              const boardX = x + c;
              const boardY = y + r;
              
              // Skip if out of bounds or above the board
              if (boardX < 0 || boardX >= (board[0]?.length || 0) || 
                  boardY < 0 || boardY >= board.length) {
                continue;
              }
              
              // Get the block color based on piece type
              let blockColor;
              if (color) {
                blockColor = { main: color, light: '#FFFFFF', dark: '#555555' };
              } else if (currentPiece.type && COLORS[shape[r][c]]) {
                blockColor = COLORS[shape[r][c]];
              } else {
                blockColor = { main: 'gray', light: '#AAA', dark: '#444' };
              }
              
              drawTGMBlock(ctx, boardX, boardY, blockColor);
            }
          }
        }
      });
    }
    
  }, [board, players, currentPlayerId]);

  return (
    <div>
      <canvas
        ref={canvasRef}
        width={canvasWidth}
        height={canvasHeight}
        style={{ 
          border: '2px solid #555',
          borderRadius: '3px',
          boxShadow: '0 0 15px rgba(0, 0, 0, 0.5)'
        }}
      />
    </div>
  );
}

export default GameBoard;