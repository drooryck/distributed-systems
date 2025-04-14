import React from 'react';

const HomeScreen = ({ 
  players, 
  currentPlayerId, 
  readyPlayers, 
  onReady, 
  onStartGame, 
  onSetGameMode, 
  gameMode,
  gameInProgress,
  isRejoining
}) => {
  const currentPlayerShortId = currentPlayerId ? currentPlayerId.substring(0, 4) : null;
  const currentPlayer = currentPlayerShortId ? Object.values(players).find(p => p.id === currentPlayerShortId) : null;
  const isPlayerOne = currentPlayer && currentPlayer.playerNumber === 1;
  
  const gameModes = [
    { id: 'classic', name: 'Classic Mode', disabled: false },
    { id: 'battle', name: 'Battle Mode', disabled: true },
    { id: 'cooperative', name: 'Co-op Mode', disabled: true }
  ];
  
  return (
    <div style={{ textAlign: 'center', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Tetristributed</h1>
      
      {gameInProgress && (
        <div style={{
          backgroundColor: '#552233',
          padding: '10px',
          borderRadius: '5px',
          marginBottom: '20px'
        }}>
          <h2>Game In Progress</h2>
          <p>A game is currently in progress. Please wait for it to finish.</p>
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
          const isPlayerRejoining = isCurrentPlayer && player.isRejoining;
          const bgColor = !player ? '#222' : '#444';
          
          return (
            <div key={num} style={{
              width: '150px',
              height: '100px',
              border: '2px solid #555',
              borderRadius: '8px',
              padding: '10px',
              backgroundColor: bgColor,
              position: 'relative',
              display: 'flex',
              flexDirection: 'column'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>
                Player {num}
                {isCurrentPlayer && ' (You)'}
              </div>
              
              <div style={{ flex: 1 }}>
                {player && isReady && (
                  <div style={{
                    width: '20px',
                    height: '20px',
                    backgroundColor: player.color,
                    margin: '0 auto'
                  }}></div>
                )}
                
                {isPlayerRejoining && (
                  <div style={{
                    position: 'absolute',
                    top: '0',
                    left: '0',
                    right: '0',
                    padding: '2px',
                    backgroundColor: '#33AA33',
                    color: 'white',
                    fontSize: '12px',
                    borderTopLeftRadius: '6px',
                    borderTopRightRadius: '6px'
                  }}>
                    Welcome Back!
                  </div>
                )}
                
                {!player && <div>Waiting for player...</div>}
                
                {player && !isReady && !isCurrentPlayer && (
                  <div style={{ fontSize: '14px', color: '#888' }}>Not Ready</div>
                )}
              </div>
              
              {isCurrentPlayer && (
                <div style={{ marginTop: 'auto' }}>
                  <button 
                    onClick={() => onReady(!isReady)}
                    style={{
                      backgroundColor: isReady ? '#333' : '#FF3333',
                      border: 'none',
                      color: 'white',
                      padding: '5px 10px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      width: '100%'
                    }}
                  >
                    {isReady ? 'Cancel' : isPlayerRejoining ? 'Rejoin Game' : 'Press X'}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      
      {isPlayerOne && (
        <div style={{ marginBottom: '30px' }}>
          <h2>Game Mode</h2>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '15px' }}>
            {gameModes.map(mode => (
              <button
                key={mode.id}
                onClick={() => !mode.disabled && onSetGameMode(mode.id)}
                style={{
                  padding: '10px 15px',
                  backgroundColor: gameMode === mode.id ? '#FF5733' : '#444',
                  border: 'none',
                  borderRadius: '4px',
                  color: 'white',
                  opacity: mode.disabled ? 0.5 : 1,
                  cursor: mode.disabled ? 'not-allowed' : 'pointer'
                }}
                disabled={mode.disabled}
              >
                {mode.name}
                {mode.disabled && ' (Coming Soon)'}
              </button>
            ))}
          </div>
        </div>
      )}
      
      {isPlayerOne && (
        <button
          onClick={onStartGame}
          style={{
            padding: '12px 30px',
            backgroundColor: readyPlayers.length > 0 ? '#33FF57' : '#555',
            border: 'none',
            borderRadius: '4px',
            color: 'white',
            fontSize: '18px',
            cursor: readyPlayers.length > 0 ? 'pointer' : 'not-allowed'
          }}
          disabled={readyPlayers.length === 0}
        >
          Start Game
        </button>
      )}
      
      {!isPlayerOne && readyPlayers.length > 0 && (
        <div style={{ marginTop: '20px', fontSize: '18px' }}>
          Waiting for Player 1 to start the game...
        </div>
      )}
      
      <div style={{ marginTop: '40px' }}>
        <h3>Controls</h3>
        <p>← → : Move left/right | ↑ or Z : Rotate | ↓ : Soft drop | Space : Hard drop</p>
      </div>
    </div>
  );
};

export default HomeScreen;