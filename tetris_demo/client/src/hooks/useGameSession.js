import { useState, useEffect, useCallback } from 'react';
import io from 'socket.io-client';
import { saveGameSession, getGameSession, clearGameSession } from '../utils/sessionStorage';

/**
 * Custom hook for managing game session and socket communication
 */
const useGameSession = () => {
  const [socket, setSocket] = useState(null);
  const [roomCode, setRoomCode] = useState('');
  const [players, setPlayers] = useState({});
  const [currentPlayer, setCurrentPlayer] = useState(null);
  const [readyPlayers, setReadyPlayers] = useState([]);
  const [gameInProgress, setGameInProgress] = useState(false);
  const [gameMode, setGameMode] = useState('classic');

  // Initialize socket connection
  useEffect(() => {
    // Connect to the socket server
    const socketConnection = io();
    setSocket(socketConnection);

    // Setup event listeners
    socketConnection.on('connect', () => {
      console.log('Connected to server with socket ID:', socketConnection.id);
    });

    socketConnection.on('disconnect', () => {
      console.log('Disconnected from server');
    });

    // Clean up socket connection when component unmounts
    return () => {
      socketConnection.disconnect();
    };
  }, []);

  // Create a new game room
  const createRoom = useCallback((playerName) => {
    if (socket) {
      socket.emit('createRoom', playerName);
    }
  }, [socket]);

  // Join an existing room
  const joinRoom = useCallback((roomCode, playerName) => {
    if (socket) {
      socket.emit('joinRoom', { roomCode, playerName });
    }
  }, [socket]);

  // Mark player as ready
  const setReady = useCallback(() => {
    if (socket && roomCode) {
      socket.emit('playerReady', { roomCode });
    }
  }, [socket, roomCode]);

  // Start the game (host only)
  const startGame = useCallback(() => {
    if (socket && roomCode) {
      socket.emit('startGame', { roomCode });
    }
  }, [socket, roomCode]);

  // Leave the current room
  const leaveRoom = useCallback(() => {
    if (socket && roomCode) {
      socket.emit('leaveRoom', { roomCode });
      clearGameSession();
      setRoomCode('');
    }
  }, [socket, roomCode]);

  // Set the game mode (classic, sprint, battle, etc.)
  const setGameModeOption = useCallback((mode) => {
    if (socket && roomCode) {
      socket.emit('setGameMode', { roomCode, gameMode: mode });
      setGameMode(mode);
    }
  }, [socket, roomCode]);

  return {
    socket,
    roomCode,
    setRoomCode,
    players,
    currentPlayer,
    readyPlayers,
    gameInProgress,
    gameMode,
    createRoom,
    joinRoom,
    setReady,
    startGame,
    leaveRoom,
    setGameMode: setGameModeOption
  };
};

export default useGameSession;