import React, { useState, useEffect } from 'react';

// Tetromino shapes for player icons
const TETRO_SHAPES = {
  I: [
    [0, 0, 0, 0],
    [1, 1, 1, 1],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
  ],
  O: [
    [0, 0, 0, 0],
    [0, 4, 4, 0],
    [0, 4, 4, 0],
    [0, 0, 0, 0]
  ],
  T: [
    [0, 0, 0, 0],
    [0, 6, 0, 0],
    [6, 6, 6, 0],
    [0, 0, 0, 0]
  ],
  L: [
    [0, 0, 0, 0],
    [0, 0, 3, 0],
    [3, 3, 3, 0],
    [0, 0, 0, 0]
  ]
};

// Tetromino colors
const TETRO_COLORS = ['#00FFFF', '#0000FF', '#FF7700', '#FFFF00', '#00FF00', '#AA00FF', '#FF0000'];
const TETRO_OUTLINES = ['#009999', '#000099', '#994700', '#999900', '#009900', '#550077', '#990000'];

const ReadyScreen = ({ 
  players, 
  currentPlayerId, 
  readyPlayers, 
  onReady, 
  onStartGame, 
  onSetGameMode,
  onLeaveRoom, 
  gameMode,
  gameInProgress,
  isRejoining,
  roomCode
}) => {
  const [bgOffset, setBgOffset] = useState(0);
  const currentPlayerShortId = currentPlayerId ? currentPlayerId.substring(0, 4) : null;
  const currentPlayer = currentPlayerShortId ? Object.values(players).find(p => p.id === currentPlayerShortId) : null;
  const isPlayerOne = currentPlayer && currentPlayer.playerNumber === 1;
  const isHost = currentPlayer && currentPlayer.isHost;
  
  // Animate background grid
  useEffect(() => {
    const interval = setInterval(() => {
      setBgOffset(prev => (prev + 1) % 40);
    }, 500);
    return () => clearInterval(interval);
  }, []);
  
  // Track X key press for ready
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key.toLowerCase() === 'x' && currentPlayer) {
        const isReady = readyPlayers.some(id => players[id] && players[id].id === currentPlayer.id);
        onReady(!isReady);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentPlayer, readyPlayers, players, onReady]);
  
  // Render tetromino shape for player icon
  const renderTetromino = (playerNum, color, ready) => {
    const tetrominoIndex = (playerNum - 1) % 4;
    const tetrominoShapes = Object.values(TETRO_SHAPES);
    const shape = tetrominoShapes[tetrominoIndex];
    const cellSize = 10;
    
    return (
      <svg width={4*cellSize} height={4*cellSize} style={{margin: '0 auto'}}>
        {shape.map((row, r) => 
          row.map((cell, c) => cell ? (
            <g key={`${r}-${c}`}>
              {/* Block body */}
              <rect 
                x={c*cellSize} 
                y={r*cellSize} 
                width={cellSize} 
                height={cellSize}
                fill={ready ? color : '#555'} 
                stroke={ready ? (color === '#FFFF00' ? '#999900' : '#333') : '#333'} 
                strokeWidth="1"
                rx="2"
                ry="2"
              />
              {/* Block highlight */}
              {ready && (
                <rect 
                  x={c*cellSize + 2} 
                  y={r*cellSize + 2} 
                  width={cellSize/2} 
                  height={cellSize/2}
                  fill="rgba(255,255,255,0.3)" 
                  rx="1"
                />
              )}
            </g>
          ) : null)
        )}
      </svg>
    );
  };
  
  return (
    <div style={{ 
      position: 'relative',
      minHeight: '100vh',
      padding: '20px',
      color: '#EEE',
      textAlign: 'center',
      background: '#121212'
    }}>
      {/* Animated grid background */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        opacity: 0.15,
        backgroundImage: `
          linear-gradient(45deg, #222 25%, transparent 25%),
          linear-gradient(-45deg, #222 25%, transparent 25%),
          linear-gradient(45deg, transparent 75%, #222 75%),
          linear-gradient(-45deg, transparent 75%, #222 75%)
        `,
        backgroundSize: '40px 40px',
        backgroundPosition: `${bgOffset}px ${bgOffset}px`,
        backgroundColor: '#181818',
        zIndex: 0
      }}/>
      
      {/* Background image */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundImage: `url(${process.env.PUBLIC_URL}/backgrounds/tetris-1920-x-1080-background-hyihqau5t3lalo4e.png)`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        opacity: 0.2,
        zIndex: 0
      }}/>
      
      <div style={{ 
        position: 'relative',
        maxWidth: '900px',
        margin: '0 auto',
        zIndex: 1
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px'
        }}>
          <h1 style={{
            fontFamily: 'Arial, sans-serif',
            fontSize: '36px',
            margin: 0,
            textShadow: '0 0 10px #66CCFF, 0 0 20px #33AADD'
          }}>
            Tetristributed
          </h1>
          
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end'
          }}>
            <div style={{
              background: 'rgba(50, 50, 80, 0.7)',
              padding: '8px 12px',
              borderRadius: '5px',
              fontSize: '16px',
              fontWeight: 'bold',
              marginBottom: '8px'
            }}>
              Room: <span style={{color: '#FFCC00'}}>{roomCode}</span>
            </div>
            
            <button 
              onClick={onLeaveRoom}
              style={{
                padding: '5px 12px',
                fontSize: '14px',
                background: 'linear-gradient(to bottom, #555, #333)',
                color: '#ccc',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Leave Room
            </button>
          </div>
        </div>
        
        {gameInProgress && (
          <div style={{
            background: 'linear-gradient(135deg, #552233, #441122)',
            padding: '12px',
            borderRadius: '6px',
            marginBottom: '25px'
          }}>
            <h2 style={{margin: '0 0 10px'}}>Game In Progress</h2>
            <p style={{margin: 0}}>Please wait for the current game to finish.</p>
          </div>
        )}
        
        {currentPlayer && !gameInProgress && (
          <div style={{
            marginBottom: '15px',
            padding: '8px',
            fontSize: '16px',
            color: '#FFCC00'
          }}>
            Press <span style={{
              display: 'inline-block',
              background: '#333',
              color: 'white',
              padding: '2px 8px',
              borderRadius: '4px',
              margin: '0 4px',
              fontWeight: 'bold',
              boxShadow: '0 2px 4px rgba(0,0,0,0.5)'
            }}>X</span> or click the READY button to get ready
          </div>
        )}
        
        <div style={{ 
          display: 'flex', 
          justifyContent: 'center', 
          marginBottom: '40px',
          flexWrap: 'wrap',
          gap: '20px'
        }}>
          {[1, 2, 3, 4].map(num => {
            const player = Object.values(players).find(p => p.playerNumber === num);
            const isReady = player && readyPlayers.some(id => players[id] && players[id].id === player.id);
            const isCurrentPlayer = player && currentPlayerShortId && player.id === currentPlayerShortId;
            
            return (
              <div key={num} style={{
                width: '180px',
                height: '180px',
                background: 'linear-gradient(135deg, #2a2a2a, #222)',
                borderRadius: '10px',
                border: `3px solid ${isReady ? '#33ee66' : '#444'}`,
                position: 'relative',
                padding: '12px',
                boxShadow: isCurrentPlayer 
                  ? `0 0 15px ${isReady ? '#33ee66' : '#ffcc00'}`
                  : 'none',
                transition: 'all 0.3s ease',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column'
              }}>
                {/* Player number indicator */}
                <div style={{
                  position: 'absolute',
                  top: '5px',
                  left: '5px',
                  background: isReady ? TETRO_COLORS[(num-1) % TETRO_COLORS.length] : '#444',
                  color: '#000',
                  width: '24px',
                  height: '24px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '50%',
                  fontWeight: 'bold',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
                }}>
                  {num}
                </div>
                
                {/* Host indicator */}
                {player && player.isHost && (
                  <div style={{
                    position: 'absolute',
                    top: '5px',
                    right: '5px',
                    background: '#FFD700',
                    color: '#000',
                    padding: '2px 8px',
                    fontSize: '12px',
                    borderRadius: '10px',
                    fontWeight: 'bold'
                  }}>
                    HOST
                  </div>
                )}
                
                {/* Player name */}
                <div style={{
                  height: '30px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 'bold',
                  fontSize: '16px'
                }}>
                  {player ? (player.name || (isCurrentPlayer ? '⭐ You ⭐' : `Player ${num}`)) : ''}
                </div>

                {/* Tetromino icon - fixed position */}
                <div style={{
                  flex: 1,
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center'
                }}>
                  {player ? (
                    renderTetromino(num, player.color, isReady)
                  ) : (
                    <span style={{color: '#888', fontSize: '16px'}}>
                      Waiting for player...
                    </span>
                  )}
                </div>

                {/* Fixed height area for button or empty space */}
                <div style={{height: '45px', marginTop: '5px'}}>
                  {isCurrentPlayer && (
                    <button 
                      onClick={() => onReady(!isReady)} 
                      style={{
                        width: '100%',
                        padding: '10px',
                        border: 'none',
                        borderRadius: '5px',
                        background: isReady 
                          ? 'linear-gradient(to bottom, #55aa55, #338833)'
                          : 'linear-gradient(to bottom, #aa5555, #883333)',
                        color: '#fff',
                        cursor: 'pointer',
                        fontWeight: 'bold',
                        boxShadow: '0 3px 6px rgba(0,0,0,0.3)',
                        transition: 'all 0.2s ease'
                      }}
                    >
                      {isReady ? 'Cancel' : 'READY!'}
                    </button>
                  )}
                </div>

                {/* Player ID */}
                {player && (
                  <div style={{
                    position: 'absolute',
                    bottom: '5px',
                    right: '5px',
                    fontSize: '10px',
                    color: '#999'
                  }}>
                    ID: {player.id.substring(0,4)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        
        {isHost && (
          <button
            onClick={onStartGame}
            disabled={readyPlayers.length === 0}
            style={{
              padding: '15px 40px',
              fontSize: '22px',
              background: readyPlayers.length
                ? 'linear-gradient(to bottom, #44ff66, #33cc55)'
                : 'linear-gradient(to bottom, #555, #444)',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: readyPlayers.length ? 'pointer' : 'not-allowed',
              fontWeight: 'bold',
              boxShadow: readyPlayers.length 
                ? '0 4px 10px rgba(40,200,70,0.4)' 
                : 'none',
              transition: 'all 0.3s ease',
              textTransform: 'uppercase'
            }}
          >
            Start Game
          </button>
        )}
        
        {!isHost && readyPlayers.length > 0 && (
          <div style={{ 
            marginTop: '20px', 
            fontSize: '18px',
            color: '#FFCC00',
            textShadow: '0 0 5px rgba(255,204,0,0.5)'
          }}>
            Waiting for Host to start the game...
          </div>
        )}
        
        <div style={{ 
          marginTop: '40px',
          backgroundColor: 'rgba(0,0,0,0.3)',
          borderRadius: '8px',
          padding: '15px',
          maxWidth: '600px',
          margin: '40px auto 0'
        }}>
          <h3 style={{
            margin: '0 0 10px',
            color: '#AACCFF'
          }}>Controls</h3>
          <p style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            gap: '15px',
            margin: 0
          }}>
            <span>← → : Move left/right</span>
            <span>↑ or Z : Rotate</span>
            <span>↓ : Soft drop</span>
            <span>Space : Hard drop</span>
            <span>X : Ready up</span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default ReadyScreen;