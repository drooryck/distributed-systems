import React from 'react';

const HomeScreen = ({ 
  players, 
  currentPlayerId, 
  readyPlayers, 
  onReady, 
  onStartGame, 
  onSetGameMode, 
  gameMode 
}) => {
  // Add safety check for currentPlayerId
  const currentPlayerShortId = currentPlayerId ? currentPlayerId.substring(0, 4) : null;
  
  // Get the current player
  const currentPlayer = currentPlayerShortId ? 
    Object.values(players).find(p => p.id === currentPlayerShortId) : 
    null;
  
  // Determine if the current player is player 1
  const isPlayerOne = currentPlayer && currentPlayer.playerNumber === 1;
  
  // Available game modes
  const gameModes = [
    { id: 'classic', name: 'Classic Mode', disabled: false },
    { id: 'battle', name: 'Battle Mode', disabled: true },
    { id: 'cooperative', name: 'Co-op Mode', disabled: true }
  ];
  
  return (
    <div style={{ 
      textAlign: 'center', 
      maxWidth: '800px',
      margin: '0 auto'
    }}>
      <h1>Tetristributed</h1>
      
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        marginBottom: '40px',
        flexWrap: 'wrap',
        gap: '20px'
      }}>
        {/* Display player slots (up to 4) */}
        {[1, 2, 3, 4].map(num => {
          const player = Object.values(players).find(p => p.playerNumber === num);
          const isReady = player && readyPlayers.includes(player.id);
          const isCurrentPlayer = player && currentPlayerShortId && player.id === currentPlayerShortId;
          
          return (
            <div key={num} style={{
              width: '150px',
              height: '100px',
              border: '2px solid #555',
              borderRadius: '8px',
              padding: '10px',
              backgroundColor: !player ? '#333' : isReady ? '#FF3333' : '#444',
              position: 'relative'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '10px' }}>
                Player {num}
                {isCurrentPlayer && ' (You)'}
              </div>
              
              {player && (
                <>
                  <div style={{
                    width: '20px',
                    height: '20px',
                    backgroundColor: player.color,
                    margin: '0 auto 10px'
                  }}></div>
                  
                  {isCurrentPlayer && (
                    <button 
                      onClick={() => onReady(!isReady)}
                      style={{
                        backgroundColor: isReady ? '#333' : '#FF3333',
                        border: 'none',
                        color: 'white',
                        padding: '5px 10px',
                        borderRadius: '4px',
                        cursor: 'pointer'
                      }}
                    >
                      {isReady ? 'Cancel' : 'Press X to Join'}
                    </button>
                  )}
                </>
              )}
              
              {!player && <div>Waiting for player...</div>}
            </div>
          );
        })}
      </div>
      
      {/* Game mode selection - only visible to player 1 */}
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
      
      {/* Start game button - only visible to player 1 */}
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