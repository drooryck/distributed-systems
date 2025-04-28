const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const ClusterNode = require('./ClusterNode');

/**
 * ClusterServer integrates the ClusterNode functionality with the Tetris server
 * It manages state replication and client connections, ensuring failover capabilities
 */
class ClusterServer {
  constructor(nodeId, configPath) {
    this.nodeId = nodeId;
    
    // Load cluster configuration
    try {
      this.clusterConfig = JSON.parse(fs.readFileSync(configPath));
    } catch (err) {
      console.error('Failed to load cluster configuration:', err);
      process.exit(1);
    }
    
    if (!this.clusterConfig.nodes || !this.clusterConfig.nodes[nodeId]) {
      console.error(`No configuration found for node ${nodeId}`);
      process.exit(1);
    }
    
    // Get node configuration
    this.nodeConfig = this.clusterConfig.nodes[nodeId];
    
    // Create Express app and HTTP server
    this.app = express();
    this.app.use(cors());
    this.server = http.createServer(this.app);
    
    // Configure static file serving
    this.app.use(express.static(path.join(__dirname, '../../../client/build')));
    
    // Initialize Socket.IO with CORS settings
    this.io = socketIO(this.server, {
      cors: {
        origin: "*",
        methods: ["GET", "POST"]
      }
    });
    
    // Initialize cluster node
    this.clusterNode = new ClusterNode(nodeId, this.nodeConfig, this.clusterConfig);
    
    // Map of all connected clients
    this.clients = new Map();
    
    // Game state storage - will be identical on all nodes
    this.rooms = {};
    this.roomGameLoops = {};
    
    // Whether we need to migrate clients when becoming leader
    this.needsMigration = false;
    
    // Bind event handlers
    this.clusterNode.on('becameLeader', this.handleBecameLeader.bind(this));
    this.clusterNode.on('leaderChanged', this.handleLeaderChanged.bind(this));
    this.clusterNode.on('stateUpdate', this.handleStateUpdate.bind(this));
    this.clusterNode.on('clientRequest', this.handleClientRequest.bind(this));
  }
  
  /**
   * Initialize the server and start listening
   */
  initialize(gameStateFunctions) {
    // Store game state functions
    this.gameStateFunctions = gameStateFunctions;
    
    // Socket.IO event handlers for client connections
    this.io.on('connection', this.handleClientConnection.bind(this));
    
    // Start the cluster node
    this.clusterNode.start();
    
    return this;
  }
  
  /**
   * Start the server
   */
  start() {
    const port = this.nodeConfig.port || process.env.PORT || 3001;
    const host = this.nodeConfig.ip || '0.0.0.0';
    
    this.server.listen(port, host, () => {
      console.log(`[Node ${this.nodeId}] Tetris server running on ${host}:${port}`);
    });
    
    return this;
  }
  
  /**
   * Handle client connection
   */
  handleClientConnection(socket) {
    console.log(`[Node ${this.nodeId}] Client connected: ${socket.id}`);
    
    // Keep track of connected clients
    this.clients.set(socket.id, socket);


    
    // If we're not the leader, provide leader information to client
    if (!this.clusterNode.isLeader && this.clusterNode.currentLeader) {
      const leaderConfig = this.clusterConfig.nodes[this.clusterNode.currentLeader];
      socket.emit('leaderInfo', {
        isLeader: false,
        leaderAddress: leaderConfig.address
      });
    } else {
      socket.emit('leaderInfo', {
        isLeader: this.clusterNode.isLeader
      });
    }
    
    // Initialize client state
    socket.emit('init', { 
      appPhase: 'homescreen',
      socketId: socket.id
    });
    
    // Send initial game state so client can render homescreen
    socket.emit('gameState', {
      appPhase: 'homescreen',
      players: {},
      roomCode: null,
      activePlayers: [],
      readyPlayers: []
    });
    
    // Handle client requests
    this.setupSocketHandlers(socket);
    
    // Clean up on disconnect
    socket.on('disconnect', () => {
      console.log(`[Node ${this.nodeId}] Client disconnected: ${socket.id}`);
      this.clients.delete(socket.id);
      
      // Handle room cleanup if player was in a room
      if (socket.roomCode && this.rooms[socket.roomCode]) {
        this.leaveRoom(socket);
      }
    });

    // Handle getLeaderInfo request
    socket.on('getLeaderInfo', () => {
      console.log(`[Node ${this.nodeId}] [CLIENT] Client requested leader information`);
      
      if (this.clusterNode.isLeader) {
        // This node is the leader, inform the client
        socket.emit('leaderInfo', {
          isLeader: true,
          leaderId: this.clusterNode.nodeId,
          address: this.nodeConfig.address || `http://localhost:${this.nodeConfig.port}`
        });
        console.log(`[Node ${this.nodeId}] [CLIENT] Informed client that I am the leader`);
      } else if (this.clusterNode.currentLeader) {
        // This node knows who the leader is, redirect the client
        const leaderId = this.clusterNode.currentLeader;
        if (this.clusterConfig.nodes[leaderId]) {
          const leaderAddress = this.clusterConfig.nodes[leaderId].address;
          socket.emit('leaderInfo', {
            isLeader: false,
            leaderId: leaderId,
            leaderAddress: leaderAddress
          });
          console.log(`[Node ${this.nodeId}] [CLIENT] Redirected client to leader ${leaderId} at ${leaderAddress}`);
        } else {
          // Leader ID is known but address info is not available
          socket.emit('leaderInfo', {
            isLeader: false,
            leaderId: leaderId,
            leaderElectionInProgress: false
          });
        }
      } else {
        // No leader known yet
        socket.emit('leaderInfo', {
          isLeader: false,
          leaderId: null,
          leaderElectionInProgress: true
        });
        console.log(`[Node ${this.nodeId}] [CLIENT] Informed client that no leader is known yet`);
      }
    });
  }
  
  /**
   * Setup socket event handlers for a client
   */
  setupSocketHandlers(socket) {
    // CREATE ROOM
    socket.on('createRoom', (playerName) => {
      if (this.clusterNode.isLeader) {
        // if already in a room, leave first
        if (socket.roomCode) this.leaveRoom(socket);

        const roomCode = this.createRoom(socket.id, playerName);
        socket.roomCode = roomCode;
        socket.join(roomCode);

        console.log(`[Node ${this.nodeId}] Player ${socket.id} created room ${roomCode}`);
        socket.emit('roomCreated', {
          roomCode,
          gameState: this.rooms[roomCode].gameState
        });
      } else {
        this.clusterNode.forwardToLeader({
          type: 'createRoom',
          socketId: socket.id,
          playerName
        });
      }
    });

    // JOIN ROOM
    socket.on('joinRoom', ({ roomCode, playerName }) => {
      if (this.clusterNode.isLeader) {
        this.handleJoinRoom(socket, roomCode, playerName);
      } else {
        this.clusterNode.forwardToLeader({
          type: 'joinRoom',
          socketId: socket.id,
          roomCode,
          playerName
        });
      }
    });

    // LEAVE ROOM
    socket.on('leaveRoom', () => {
      if (this.clusterNode.isLeader) {
        this.leaveRoom(socket);
        socket.emit('roomLeft', { appPhase: 'homescreen' });
      } else {
        this.clusterNode.forwardToLeader({
          type: 'leaveRoom',
          socketId: socket.id
        });
      }
    });

    // PLAYER READY
    socket.on('playerReady', (isReady) => {
      if (this.clusterNode.isLeader) {
        this.handlePlayerReady(socket, isReady);
      } else {
        this.clusterNode.forwardToLeader({
          type: 'playerReady',
          socketId: socket.id,
          isReady
        });
      }
    });

    // SET GAME MODE
    socket.on('setGameMode', (mode) => {
      if (this.clusterNode.isLeader) {
        this.handleSetGameMode(socket, mode);
      } else {
        this.clusterNode.forwardToLeader({
          type: 'setGameMode',
          socketId: socket.id,
          mode
        });
      }
    });

    // START GAME
    socket.on('startGame', () => {
      if (this.clusterNode.isLeader) {
        this.handleStartGame(socket);
      } else {
        this.clusterNode.forwardToLeader({
          type: 'startGame',
          socketId: socket.id
        });
      }
    });

    // PLAYER ACTIONS (move, drop, rotate, DAS, etc.)
    socket.on('playerAction', (action) => {
      if (this.clusterNode.isLeader) {
        this.handlePlayerAction(socket, action);
      } else {
        this.clusterNode.forwardToLeader({
          type: 'playerAction',
          socketId: socket.id,
          action
        });
      }
    });
  }

  
  
  /**
   * Handle when this node becomes the leader
   */
  handleBecameLeader() {
    console.log(`[Node ${this.nodeId}] Handling leader transition`);
    
    // Notify all connected clients that we're the leader now
    for (const [socketId, socket] of this.clients.entries()) {
      socket.emit('leaderInfo', { isLeader: true });
    }
    
    // If we have state we need to recover, set up game loops
    for (const roomCode in this.rooms) {
      if (this.rooms[roomCode] && !this.roomGameLoops[roomCode]) {
        // Restart game state update loop
        this.startGameStateUpdateLoop(roomCode);
      }
    }
  }
  
  /**
   * Handle when the leader changes
   */
  handleLeaderChanged(newLeaderId) {
    console.log(`[Node ${this.nodeId}] Leader changed to: ${newLeaderId}`);
    
    // If we have active client connections, inform them about the new leader
    if (this.clients.size > 0 && newLeaderId && newLeaderId !== this.nodeId) {
      const leaderConfig = this.clusterConfig.nodes[newLeaderId];
      
      for (const [socketId, socket] of this.clients.entries()) {
        socket.emit('leaderInfo', {
          isLeader: false,
          leaderAddress: leaderConfig.address
        });
      }
    }
  }
  
  /**
   * Handle state update from the leader
   */
  handleStateUpdate(roomCode, gameState) {
    console.log(`[Node ${this.nodeId}] [STATE] Received state update for room ${roomCode}`);
    
    // Update our local room state
    if (!this.rooms[roomCode]) {
      // Create the room if it doesn't exist
      console.log(`[Node ${this.nodeId}] [STATE] Creating new room ${roomCode} from state update`);
      this.rooms[roomCode] = {
        gameState: gameState,
        createdAt: Date.now(),
        lastActivity: Date.now()
      };
      
      // Start game state update loop if we're the leader
      if (this.clusterNode.isLeader && !this.roomGameLoops[roomCode]) {
        this.startGameStateUpdateLoop(roomCode);
      }
    } else {
      // Update existing room
      this.rooms[roomCode].gameState = gameState;
      this.rooms[roomCode].lastActivity = Date.now();
      console.log(`[Node ${this.nodeId}] [STATE] Updated state for room ${roomCode}`);
    }
    
    // If we're not the leader, broadcast the updated state to clients in this room
    if (!this.clusterNode.isLeader) {
      this.io.to(roomCode).emit('gameState', gameState);
    }
  }
  
  /**
   * Handle client request forwarded from a follower
   */
  handleClientRequest(request) {
    // Get the socket for the client
    const socket = this.clients.get(request.socketId);
    if (!socket) return;
    
    console.log(`[Node ${this.nodeId}] Handling forwarded client request: ${request.type}`);
    
    switch (request.type) {
      case 'createRoom':
        if (socket.roomCode) {
          this.leaveRoom(socket);
        }
        
        const roomCode = this.createRoom(socket.id, request.playerName);
        socket.roomCode = roomCode;
        socket.join(roomCode);
        
        socket.emit('roomCreated', { 
          roomCode,
          gameState: this.rooms[roomCode].gameState
        });
        break;
        
      case 'joinRoom':
        this.handleJoinRoom(socket, request.roomCode, request.playerName);
        break;
        
      case 'leaveRoom':
        this.leaveRoom(socket);
        socket.emit('roomLeft', { appPhase: 'homescreen' });
        break;
        
      case 'playerReady':
        this.handlePlayerReady(socket, request.isReady);
        break;
        
      case 'setGameMode':
        this.handleSetGameMode(socket, request.mode);
        break;
        
      case 'startGame':
        this.handleStartGame(socket);
        break;
        
      case 'playerAction':
        this.handlePlayerAction(socket, request.action);
        break;
    }
  }
  
  /**
   * Create a new room
   */
  createRoom(socketId, playerName) {
    // Generate a unique room code
    let roomCode;
    do {
      roomCode = this.generateRoomCode();
    } while (this.rooms[roomCode]);
    
    // Create new game state for the room
    const roomGameState = this.gameStateFunctions.createGameState();
    roomGameState.roomCode = roomCode;
    roomGameState.appPhase = 'readyscreen';
    
    // Add the creator as the first player and host
    roomGameState.players = {};
    roomGameState.activePlayers = new Set([socketId]);
    roomGameState.readyPlayers = [];
    
    // Add player to game state with host privileges
    roomGameState.players[socketId] = {
      id: socketId.substring(0, 4),
      playerNumber: 1,
      isHost: true,
      name: playerName || `Player 1`,
      isReady: false,
      color: roomGameState.playerColors[0],
      score: 0
    };
    
    // Store room in rooms object
    this.rooms[roomCode] = {
      gameState: roomGameState,
      createdAt: Date.now(),
      lastActivity: Date.now()
    };
    
    
    // Replicate to followers
    this.clusterNode.replicateState(roomGameState, roomCode);
    
    return roomCode;
  }
  
  /**
   * Generate a 6-character room code
   */
  generateRoomCode() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let result = '';
    for (let i = 0; i < 6; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }
  
  /**
   * Start game state update loop for a room
   */
  startGameStateUpdateLoop(roomCode) {
    // Clean up existing loop if there is one
    if (this.roomGameLoops[roomCode]) {
      clearInterval(this.roomGameLoops[roomCode]);
    }
    
    // Start a simple game state update loop for this room
    this.roomGameLoops[roomCode] = setInterval(() => {
      // Only send updates if there are players in the room and the room still exists
      if (this.rooms[roomCode] && this.rooms[roomCode].gameState.activePlayers.size > 0) {
        // Only the leader updates game state
        if (this.clusterNode.isLeader) {
          // Handle game state updates
          if (this.rooms[roomCode].gameState.appPhase === 'playing') {
            this.updateRoomGameState(roomCode);
          }
          
          // Send the current state to clients and replicate to followers
          this.io.to(roomCode).emit('gameState', this.rooms[roomCode].gameState);
          
          // Replicate to followers
          this.clusterNode.replicateState(this.rooms[roomCode].gameState, roomCode);
        }
      } else if (this.clusterNode.isLeader) {
        // Cleanup room if empty
        this.cleanupRoom(roomCode);
      }
    }, 1000 / 60); // 60 FPS
  }
  
  /**
   * Update game state for a room
   */
  updateRoomGameState(roomCode) {
    if (!this.rooms[roomCode]) return;
    
    // Call the game logic function to update the room state
    // This would be the same logic from your original updateRoomGameState function
    // For now, let's assume we're adapting that to this class
    
    // Example implementation (you'll need to add the full logic):
    const gameState = this.rooms[roomCode].gameState;
    
    // Handle ongoing line clear animation
    if (gameState.lineClearActive) {
      gameState.lineClearTimer++;
      
      // After animation completes, clear the lines
      if (gameState.lineClearTimer >= 30) { // 30 frames = 0.5 seconds at 60fps
        const newBoard = [...gameState.board];
        
        // Remove cleared lines
        for (const row of gameState.linesToClear.sort((a, b) => b - a)) {
          newBoard.splice(row, 1);
          newBoard.unshift(new Array(newBoard[0].length).fill(0));
        }
        
        gameState.board = newBoard;
        gameState.lineClearActive = false;
        gameState.linesToClear = [];
      }
    }
    
    // Process each active player
    Array.from(gameState.activePlayers).forEach(playerId => {
      const player = gameState.players[playerId];
      if (!player || !player.currentPiece) return;
      
      // The rest of your game state update logic goes here
      // ...
    });
    
    // Update room last activity time
    this.rooms[roomCode].lastActivity = Date.now();
  }
  
  /**
   * Handle player joining a room
   */
  handleJoinRoom(socket, roomCode, playerName) {
    roomCode = roomCode.toUpperCase();
    
    // If player is already in a room, make them leave first
    if (socket.roomCode) {
      this.leaveRoom(socket);
    }
    
    // Check if room exists
    if (!this.rooms[roomCode]) {
      socket.emit('error', { message: 'Room not found.' });
      return;
    }
    
    // Check if game in progress
    if (this.rooms[roomCode].gameState.appPhase === 'playing') {
      socket.emit('error', { message: 'Game in progress. Please try another room.' });
      return;
    }
    
    // Add player to room
    socket.roomCode = roomCode;
    socket.join(roomCode);
    
    // Add player to room's game state
    this.rooms[roomCode].gameState = this.gameStateFunctions.handleNewPlayer(
      this.rooms[roomCode].gameState, 
      socket.id
    );
    
    // Set player name
    this.rooms[roomCode].gameState.players[socket.id].name = 
      playerName || `Player ${this.rooms[roomCode].gameState.players[socket.id].playerNumber}`;
    
    console.log(`[Node ${this.nodeId}] Player ${socket.id} joined room ${roomCode}`);
    
    // Send room info to client
    socket.emit('roomJoined', { 
      roomCode,
      gameState: this.rooms[roomCode].gameState
    });
    
    // Notify other players in room
    socket.to(roomCode).emit('playerJoined', {
      playerId: socket.id,
      player: this.rooms[roomCode].gameState.players[socket.id],
      gameState: this.rooms[roomCode].gameState
    });
    
    // Replicate to followers
    this.clusterNode.replicateState(this.rooms[roomCode].gameState, roomCode);
  }
  
  /**
   * Handle player leaving a room
   */
  leaveRoom(socket) {
    const roomCode = socket.roomCode;
    if (!roomCode || !this.rooms[roomCode]) return;
    
    const room = this.rooms[roomCode];
    const players = room.gameState.players;
    
    // Remove player from ready players
    room.gameState.readyPlayers = room.gameState.readyPlayers.filter(id => id !== socket.id);
    
    // Remove player from active players
    room.gameState.activePlayers.delete(socket.id);
    
    // Record player leaving
    const leavingPlayer = players[socket.id];
    if (leavingPlayer) {
      const wasHost = leavingPlayer.isHost;
      
      // Remove player from players object
      delete players[socket.id];
      
      console.log(`[Node ${this.nodeId}] Player ${socket.id} left room ${roomCode}`);
      
      // Notify other players
      socket.to(roomCode).emit('playerLeft', {
        playerId: socket.id,
        gameState: room.gameState
      });
      
      // If room is empty, clean it up
      if (room.gameState.activePlayers.size === 0) {
        this.cleanupRoom(roomCode);
        console.log(`[Node ${this.nodeId}] Room ${roomCode} cleaned up after last player left`);
      } 
      // If player was host, assign host to the next player
      else if (wasHost) {
        const remainingPlayers = Object.keys(players);
        if (remainingPlayers.length > 0) {
          const newHostId = remainingPlayers[0];
          players[newHostId].isHost = true;
          
          // Notify the new host
          this.io.to(newHostId).emit('hostAssigned', {
            gameState: room.gameState
          });
          
          console.log(`[Node ${this.nodeId}] New host assigned in room ${roomCode}: ${newHostId}`);
        }
      }
    }
    
    // Update room last activity
    if (room) {
      room.lastActivity = Date.now();
    }
    
    // Replicate state to followers
    if (this.clusterNode.isLeader && this.rooms[roomCode]) {
      this.clusterNode.replicateState(this.rooms[roomCode].gameState, roomCode);
    }
    
    // Remove socket from room
    socket.leave(roomCode);
    socket.roomCode = null;
  }
  
  /**
   * Clean up a room
   */
  cleanupRoom(roomCode) {
    if (this.roomGameLoops[roomCode]) {
      clearInterval(this.roomGameLoops[roomCode]);
      delete this.roomGameLoops[roomCode];
    }
    
    delete this.rooms[roomCode];
  }
  
  /**
   * Handle player ready state
   */
  handlePlayerReady(socket, isReady) {
    const roomCode = socket.roomCode;
    if (!roomCode || !this.rooms[roomCode]) return;
    
    const gameState = this.rooms[roomCode].gameState;
    const player = gameState.players[socket.id];
    if (!player) return;
    
    player.isReady = isReady;
    
    if (isReady) {
      if (!gameState.readyPlayers.includes(socket.id)) {
        gameState.readyPlayers.push(socket.id);
      }
    } else {
      gameState.readyPlayers = gameState.readyPlayers.filter(id => id !== socket.id);
    }
    
    // Broadcast to room
    this.io.to(roomCode).emit('gameState', gameState);
    
    // Replicate to followers
    this.clusterNode.replicateState(gameState, roomCode);
  }
  
  /**
   * Handle game mode changes
   */
  handleSetGameMode(socket, mode) {
    const roomCode = socket.roomCode;
    if (!roomCode || !this.rooms[roomCode]) return;
    
    const gameState = this.rooms[roomCode].gameState;
    const player = gameState.players[socket.id];
    
    // Only host can change game mode
    if (player && player.isHost) {
      gameState.gameMode = mode;
      this.io.to(roomCode).emit('gameState', gameState);
      
      // Replicate to followers
      this.clusterNode.replicateState(gameState, roomCode);
    }
  }
  
  /**
   * Handle game start
   */
  handleStartGame(socket) {
    const roomCode = socket.roomCode;
    if (!roomCode || !this.rooms[roomCode]) return;
    
    const gameState = this.rooms[roomCode].gameState;
    const player = gameState.players[socket.id];
    
    // Only host can start the game
    if (player && player.isHost) {
      console.log(`[Node ${this.nodeId}] Game started in room ${roomCode} by host ${socket.id}`);
      this.startGame(roomCode);
    }
  }
  
  /**
   * Start a game in a room
   */
  startGame(roomCode) {
    if (!this.rooms[roomCode]) return;
    
    const room = this.rooms[roomCode];
    room.gameState.appPhase = 'playing';
    room.gameState.gameInProgress = true;
    
    // Only use ready players for the game
    const readyPlayers = Object.keys(room.gameState.players).filter(id => 
      room.gameState.readyPlayers.includes(id));
    
    // Get the count of ONLY READY players
    const readyPlayerCount = readyPlayers.length;
    console.log(`[Node ${this.nodeId}] Starting game in room ${roomCode} with ${readyPlayerCount} ready players`);
    
    // Get board dimensions based on READY players only
    const { rows, cols } = this.gameStateFunctions.getBoardDimensions(readyPlayerCount);
    room.gameState.board = this.gameStateFunctions.createEmptyBoard(rows, cols);
    
    // Update activePlayers set with only ready players
    room.gameState.activePlayers = new Set(readyPlayers);
    
    // Initialize only ready players for the game
    readyPlayers.forEach((id, index) => {
      // Calculate spawn position
      const spawnPos = this.getSpawnPosition(index, cols, readyPlayerCount);
      
      // Initialize player state
      room.gameState.players[id].score = 0;
      room.gameState.players[id].x = spawnPos.x;
      room.gameState.players[id].y = spawnPos.y;
      room.gameState.players[id].currentPiece = this.gameStateFunctions.getRandomTetromino();
      room.gameState.players[id].isWaitingForNextPiece = false;
      room.gameState.players[id].isLocking = false;
      room.gameState.players[id].lockTimer = 0;
      room.gameState.players[id].fallTimer = room.gameState.players[id].fallSpeed - 1;
      room.gameState.players[id].fallSpeed = 45;
      room.gameState.players[id].softDropSpeed = 5;
      room.gameState.players[id].justPerformedHardDrop = false;
      
      console.log(`[Node ${this.nodeId}] Player ${id} (index ${index}) spawning at position (${spawnPos.x}, ${spawnPos.y})`);
    });
    
    // Update room activity
    room.lastActivity = Date.now();
    
    // Replicate to followers
    this.clusterNode.replicateState(room.gameState, roomCode);
  }
  
  /**
   * Get spawn position based on player index and board size
   */
  getSpawnPosition(playerIndex, boardWidth, totalPlayers) {
    // For single player, spawn in the middle
    if (totalPlayers === 1) return { x: Math.floor(boardWidth / 2) - 2, y: 0 };
    
    // For multiple players, divide the board into equal sections
    const sectionWidth = Math.floor(boardWidth / totalPlayers);
    return {
      x: playerIndex * sectionWidth + Math.floor(sectionWidth / 2) - 2,
      y: 0
    };
  }
  
  /**
   * Handle player actions
   */
  handlePlayerAction(socket, action) {
    const roomCode = socket.roomCode;
    if (!roomCode || !this.rooms[roomCode]) return;
    
    const gameState = this.rooms[roomCode].gameState;
    
    // Only process actions from active players
    if (gameState.appPhase === 'playing' && 
        gameState.activePlayers.has(socket.id) &&
        gameState.readyPlayers.includes(socket.id)) {
      
      // Update the room's game state
      this.rooms[roomCode].gameState = this.gameStateFunctions.handlePlayerAction(
        gameState, 
        socket.id, 
        action
      );
      
      // No need to send an update here, as the game loop will handle that
    } else {
      console.log(`[Node ${this.nodeId}] Ignored action from non-active player: ${socket.id} in room ${roomCode}`);
    }
  }
  
  /**
   * Clean up resources when shutting down
   */
  shutdown() {
    console.log(`[Node ${this.nodeId}] Shutting down Tetris server`);
    
    // Shut down cluster node
    this.clusterNode.shutdown();
    
    // Clean up game loops
    Object.keys(this.roomGameLoops).forEach(roomCode => {
      if (this.roomGameLoops[roomCode]) {
        clearInterval(this.roomGameLoops[roomCode]);
      }
    });
    
    // Close server
    if (this.server) {
      this.server.close();
    }
  }
}

module.exports = ClusterServer;