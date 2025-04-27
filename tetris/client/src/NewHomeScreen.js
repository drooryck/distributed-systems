import React, { useState } from 'react';
import './HomeScreen.css';

const NewHomeScreen = ({ onCreateRoom, onJoinRoom, error }) => {
  const [playerName, setPlayerName] = useState('');
  const [roomCode, setRoomCode] = useState('');
  const [view, setView] = useState('main'); // 'main', 'create', 'join'
  const [nameError, setNameError] = useState('');

  // Handle player name input
  const handleNameChange = (e) => {
    setPlayerName(e.target.value);
    if (nameError) setNameError('');
  };

  // Handle room code input
  const handleRoomCodeChange = (e) => {
    // Convert to uppercase and remove any non-alphanumeric characters
    setRoomCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''));
  };

  // Validate player name before proceeding
  const validateName = () => {
    if (!playerName.trim()) {
      setNameError('Please enter your name');
      return false;
    }
    return true;
  };

  // Handle create room button
  const handleCreateRoom = () => {
    if (validateName()) {
      onCreateRoom(playerName);
    }
  };

  // Handle join room button
  const handleJoinRoom = () => {
    if (validateName() && roomCode.length === 6) {
      onJoinRoom(roomCode, playerName);
    }
  };

  return (
    <div className="homescreen">
      <div className="homescreen-container">
        <h1 className="game-title">TETRISTRIBUTED</h1>
        <div className="game-subtitle">Multiplayer Tetris</div>
        
        {view === 'main' && (
          <div className="main-menu">
            <div className="player-name-input">
              <label htmlFor="playerName">Your Name</label>
              <input
                type="text"
                id="playerName"
                value={playerName}
                onChange={handleNameChange}
                placeholder="Enter your name"
                maxLength={15}
              />
              {nameError && <div className="error-message">{nameError}</div>}
            </div>
            
            <div className="buttons-container">
              <button 
                className="menu-button create-button"
                onClick={() => validateName() && handleCreateRoom()}
              >
                Create Room
              </button>
              <div className="button-separator">or</div>
              <button 
                className="menu-button join-button"
                onClick={() => validateName() && setView('join')}
              >
                Join Room
              </button>
            </div>
          </div>
        )}

        {view === 'join' && (
          <div className="join-room">
            <h2>Join a Room</h2>
            
            <div className="room-code-input">
              <label htmlFor="roomCode">Room Code</label>
              <input
                type="text"
                id="roomCode"
                value={roomCode}
                onChange={handleRoomCodeChange}
                placeholder="Enter 6-digit code"
                maxLength={6}
              />
            </div>
            
            <div className="buttons-container">
              <button 
                className="menu-button join-button"
                onClick={handleJoinRoom}
                disabled={roomCode.length !== 6}
              >
                Join Game
              </button>
              <button 
                className="menu-button back-button"
                onClick={() => setView('main')}
              >
                Back
              </button>
            </div>
            
            {error && <div className="error-message">Error: {error}</div>}
          </div>
        )}
        
        <div className="footer">
          <div className="controls-info">
            <h3>Controls</h3>
            <div className="controls-list">
              <div className="control-item">
                <span className="key">←</span>
                <span className="key">→</span> Move
              </div>
              <div className="control-item">
                <span className="key">↑</span>
                <span className="key">Z</span> Rotate
              </div>
              <div className="control-item">
                <span className="key">↓</span> Soft Drop
              </div>
              <div className="control-item">
                <span className="key">Space</span> Hard Drop
              </div>
              <div className="control-item">
                <span className="key">X</span> Ready Up
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NewHomeScreen;