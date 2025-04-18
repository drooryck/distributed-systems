import React, { useEffect, useState } from 'react';

const GameOverScreen = ({ gameOverData, onTimeout }) => {
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
  
  // Format the player ID to be more readable
  const playerShortId = gameOverData.playerId ? gameOverData.playerId.substring(0, 4) : 'Unknown';
  
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
        <h2 style={{ margin: '0 0 20px', fontSize: '28px', color: '#FF5733' }}>Game Over</h2>
        
        <div style={{ fontSize: '18px', marginBottom: '15px' }}>
          Player <span style={{ fontWeight: 'bold', color: '#FF5733' }}>{playerShortId}</span> lost!
        </div>
        
        <div style={{ fontSize: '24px', margin: '20px 0' }}>
          Final Score: <span style={{ fontWeight: 'bold' }}>{gameOverData.score}</span>
        </div>
        
        <div style={{ fontSize: '16px', marginTop: '25px', color: '#AAA' }}>
          Returning to lobby in {countdown} seconds...
        </div>
      </div>
    </div>
  );
};

export default GameOverScreen;