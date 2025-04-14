import React, { useState, useEffect } from 'react';

const ScorePanel = ({ score = 0, level = 1, lastScoreChange = 0, elapsedTime = 0 }) => {
  const [isFlashing, setIsFlashing] = useState(false);
  
  // Flash animation when score changes
  useEffect(() => {
    if (lastScoreChange > 0) {
      setIsFlashing(true);
      const timer = setTimeout(() => setIsFlashing(false), 500);
      return () => clearTimeout(timer);
    }
  }, [lastScoreChange]);

  // Format time as MM:SS:CC
  const formatTime = (timeInMs) => {
    const minutes = Math.floor(timeInMs / 60000);
    const seconds = Math.floor((timeInMs % 60000) / 1000);
    const centiseconds = Math.floor((timeInMs % 1000) / 10);
    
    return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}:${centiseconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="score-panel" style={{ 
      backgroundColor: '#222',
      color: '#fff',
      padding: '12px 15px',
      borderRadius: '8px',
      fontFamily: 'monospace',
      boxShadow: '0 0 10px rgba(0, 0, 0, 0.5)',
      width: '100%',
      maxWidth: '320px',
      margin: '5px 0'
    }}>
      {/* Timer Display */}
      <div style={{
        textAlign: 'center',
        marginBottom: '10px',
        padding: '5px',
        backgroundColor: '#111',
        borderRadius: '5px'
      }}>
        <div style={{ fontSize: '12px', color: '#aaa', marginBottom: '2px' }}>TIME</div>
        <div style={{ 
          fontSize: '24px', 
          fontWeight: 'bold', 
          color: '#0f0',
          fontFamily: 'monospace',
          letterSpacing: '2px'
        }}>
          {formatTime(elapsedTime)}
        </div>
      </div>
      
      {/* Score Display */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        padding: '8px',
        backgroundColor: '#191919',
        borderRadius: '5px',
        marginBottom: '8px'
      }}>
        <span style={{ fontSize: '16px', color: '#aaa' }}>SCORE</span>
        <span style={{ 
          fontSize: '24px', 
          fontWeight: 'bold', 
          color: isFlashing ? '#ffcc00' : '#fff',
          transition: 'color 0.2s'
        }}>
          {score.toLocaleString()}
        </span>
      </div>
      
      {/* Level Display */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        padding: '8px',
        backgroundColor: '#191919',
        borderRadius: '5px'
      }}>
        <span style={{ fontSize: '16px', color: '#aaa' }}>LEVEL</span>
        <span style={{ 
          fontSize: '20px', 
          fontWeight: 'bold', 
          color: '#66ccff'
        }}>
          {level}
        </span>
      </div>
      
      {/* Last Score Change Display */}
      {lastScoreChange > 0 && (
        <div style={{ 
          fontSize: '18px', 
          color: '#66ff66', 
          textAlign: 'right',
          height: '24px',
          marginTop: '8px',
          fontWeight: 'bold',
          animation: 'fadeUp 1s'
        }}>
          +{lastScoreChange}
        </div>
      )}
      
      {/* Scoring Info */}
      <div style={{ 
        fontSize: '11px', 
        color: '#666', 
        marginTop: '10px',
        textAlign: 'center',
        padding: '5px',
        borderTop: '1px solid #333'
      }}>
        <div>LINES CLEARED = 100 POINTS EACH</div>
        <div>SOFT DROP = 1 POINT PER CELL</div>
        <div>HARD DROP = 2 POINTS PER CELL</div>
      </div>
    </div>
  );
};

export default ScorePanel;