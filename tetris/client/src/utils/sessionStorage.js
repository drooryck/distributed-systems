// Session storage utilities for game persistence across server failovers

const GAME_SESSION_KEY = 'tetris_game_session';

/**
 * Save the current game session data to localStorage
 * This allows clients to rejoin their game after server failover
 */
export const saveGameSession = (data) => {
  try {
    // Add timestamp and ensure all required fields are present
    const sessionData = {
      ...data,
      timestamp: Date.now(),
      // Make sure we have playerName and roomCode
      playerName: data.playerName || 'Player',
      roomCode: data.roomCode
    };
    
    localStorage.setItem(GAME_SESSION_KEY, JSON.stringify(sessionData));
    console.log('Game session saved:', sessionData);
  } catch (error) {
    console.error('Failed to save game session:', error);
  }
};

/**
 * Retrieve saved game session data from localStorage
 */
export const getGameSession = () => {
  try {
    const data = localStorage.getItem(GAME_SESSION_KEY);
    if (!data) return null;
    
    const sessionData = JSON.parse(data);
    
    // Check if session is too old (over 30 minutes)
    const MAX_SESSION_AGE = 30 * 60 * 1000; // 30 minutes
    if (sessionData.timestamp && Date.now() - sessionData.timestamp > MAX_SESSION_AGE) {
      clearGameSession();
      return null;
    }
    
    return sessionData;
  } catch (error) {
    console.error('Failed to retrieve game session:', error);
    return null;
  }
};

/**
 * Clear the saved game session data
 */
export const clearGameSession = () => {
  try {
    localStorage.removeItem(GAME_SESSION_KEY);
    console.log('Game session cleared');
  } catch (error) {
    console.error('Failed to clear game session:', error);
  }
};

/**
 * Update only specific fields in the session without changing others
 */
export const updateGameSession = (updates) => {
  try {
    const currentSession = getGameSession();
    if (!currentSession) return false;
    
    const updatedSession = {
      ...currentSession,
      ...updates,
      timestamp: Date.now() // Reset timestamp on updates
    };
    
    localStorage.setItem(GAME_SESSION_KEY, JSON.stringify(updatedSession));
    return true;
  } catch (error) {
    console.error('Failed to update game session:', error);
    return false;
  }
};