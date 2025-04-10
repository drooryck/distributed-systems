import React, { useEffect, useState } from 'react';

const GameOverScreen = ({ gameOverData }) => {
  const [countdown, setCountdown] = useState(5);
  
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => clearInterval(timer);
  }, []);

  // Handle potential missing data
  const playerId = gameOverData && gameOverData.playerId ? 
    gameOverData.playerId.substring(0, 4) : 'Unknown';
  const score = gameOverData ? gameOverData.score : 0;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 10,
      color: 'white',
      fontSize: '24px'
    }}>
      <h1 style={{ fontSize: '48px', marginBottom: '20px' }}>GAME OVER</h1>
      
      <p>Player {playerId} lost with score: {score}</p>
      
      <div style={{ marginTop: '30px' }}>
        Returning to homescreen in {countdown} seconds...
      </div>
    </div>
  );
};

export default GameOverScreen;