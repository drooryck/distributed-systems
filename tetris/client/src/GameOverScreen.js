import React, { useEffect, useState } from 'react';

const GameOverScreen = ({ gameOverData, currentPlayerId, onTimeout }) => {
  const [countdown, setCountdown] = useState(5);

  useEffect(() => {
    // Start countdown
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          onTimeout();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [onTimeout]);

  // Make sure we're accessing the correct properties
  const youLost = currentPlayerId === gameOverData.playerId;
  
  // Make sure we're explicitly checking for multiplayer mode
  const isMultiplayer = gameOverData.isMultiplayer === true;
  
  // For multiplayer games, ONLY show the total score
  const scoreToDisplay = isMultiplayer ? gameOverData.totalScore : gameOverData.score;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 1000
    }}>
      <div style={{
        backgroundColor: '#333',
        padding: '30px',
        borderRadius: '10px',
        boxShadow: '0 0 20px rgba(255, 0, 0, 0.5)',
        textAlign: 'center',
        color: 'white',
        maxWidth: '400px'
      }}>
        <h2 style={{
          margin: '0 0 20px',
          fontSize: '28px',
          color: '#FF5733'
        }}>
          Game Over
        </h2>

        {youLost && (
          <div style={{
            fontSize: '20px',
            marginBottom: '15px'
          }}>
            You lost!
          </div>
        )}

        <div style={{
          fontSize: '24px',
          margin: '20px 0'
        }}>
          {isMultiplayer ? (
            <div>
              Team Score: <span style={{ fontWeight: 'bold' }}>
                {scoreToDisplay}
              </span>
            </div>
          ) : (
            <div>
              Final Score: <span style={{ fontWeight: 'bold' }}>
                {scoreToDisplay}
              </span>
            </div>
          )}
        </div>

        <div style={{
          fontSize: '16px',
          marginTop: '25px',
          color: '#AAA'
        }}>
          Returning to lobby in {countdown}…
        </div>
      </div>
    </div>
  );
};

export default GameOverScreen;