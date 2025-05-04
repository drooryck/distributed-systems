const socketIO = require('socket.io');
const socketIOClient = require('socket.io-client');
const EventEmitter = require('events');
const fs = require('fs');
const path = require('path');

/**
 * ClusterManager handles the coordination between multiple Tetris server instances.
 * It implements:
 * - Leader election using heartbeats and lowest server ID
 * - State replication from leader to followers
 * - Fault detection
 */
class ClusterManager extends EventEmitter {
  constructor(serverId) {
    super();
    this.serverId = serverId;
    
    try {
      // Load cluster configuration
      const configPath = path.join(__dirname, '../cluster-config.json');
      this.clusterConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      this.serverConfig = this.clusterConfig.servers.find(s => s.id === serverId);
      
      if (!this.serverConfig) {
        throw new Error(`Invalid server ID: ${serverId}`);
      }
      
      // Initialize server state
      this.isLeader = false;
      this.leaderId = null;
      this.connections = {};
      this.lastHeartbeats = {};
      this.heartbeatInterval = this.clusterConfig.heartbeatInterval;
      this.heartbeatTimeout = this.clusterConfig.heartbeatTimeout;
      this.heartbeatTimer = null;
      this.monitoringTimer = null;
      this.lastStateUpdate = null;
      
      // Initialize heartbeat tracking for each server
      this.clusterConfig.servers.forEach(server => {
        if (server.id !== this.serverId) {
          this.lastHeartbeats[server.id] = 0; // No heartbeat received initially
        }
      });
      
      console.log(`Cluster manager initialized for server ${serverId}`);
    } catch (error) {
      console.error('Failed to initialize cluster manager:', error);
      throw error;
    }
  }
  
  /**
   * Initialize the cluster manager and establish connections
   */
  initialize() {
    // Set up server for cluster communication
    this.io = socketIO(this.serverConfig.clusterPort, {
      cors: { origin: "*", methods: ["GET", "POST"] }
    });
    
    console.log(`Cluster server listening on port ${this.serverConfig.clusterPort}`);
    
    // Set up connection handlers
    this.io.on('connection', (socket) => {
      console.log(`Cluster connection received from a server`);
      
      // Identify the connecting server
      socket.on('server-hello', (data) => {
        const peerId = parseInt(data.serverId);
        console.log(`Server ${peerId} connected to cluster server ${this.serverId}`);
        
        this.connections[peerId] = socket;
        
        // Listen for heartbeats
        socket.on('heartbeat', (data) => {
          this.lastHeartbeats[data.serverId] = Date.now();
          
          // If the sender claims to be leader, update our leader info
          if (data.isLeader) {
            this.leaderId = data.serverId;
            this.isLeader = (this.serverId === data.serverId);
          }
        });
        
        // Listen for state updates from leader
        socket.on('state-update', (data) => {
          if (this.isLeader) return; // Leader doesn't need updates
          
          this.lastStateUpdate = data;
          this.emit('state-update', data);
        });
        
        socket.on('disconnect', () => {
          console.log(`Server disconnected from cluster`);
          delete this.connections[peerId];
          this.checkLeadership();
        });
      });
    });
    
    // Connect to other servers
    this.connectToOtherServers();
    
    // Start heartbeats and monitoring
    this.startHeartbeat();
    this.startMonitoring();
    
    // Run initial leadership check
    this.checkLeadership();
  }
  
  /**
   * Connect to all other servers in the cluster
   */
  connectToOtherServers() {
    this.clusterConfig.servers.forEach(server => {
      if (server.id !== this.serverId) {
        const serverUrl = `http://${server.host}:${server.clusterPort}`;
        console.log(`Attempting to connect to server ${server.id} at ${serverUrl}`);
        
        try {
          const socket = socketIOClient(serverUrl);
          
          socket.on('connect', () => {
            console.log(`Connected to server ${server.id} at ${serverUrl}`);
            socket.emit('server-hello', { serverId: this.serverId });
            this.connections[server.id] = socket;
            
            // Record an initial heartbeat when connection is established
            this.lastHeartbeats[server.id] = Date.now();
            
            this.checkLeadership();
          });
          
          socket.on('heartbeat', (data) => {
            // Debug log to see heartbeats being received
            console.log(`Server ${this.serverId} received heartbeat from server ${data.serverId}`);
            this.lastHeartbeats[data.serverId] = Date.now();
            
            // If the sender claims to be leader, update our leader info
            if (data.isLeader) {
              this.leaderId = data.serverId;
              this.isLeader = (this.serverId === data.serverId);
            }
          });  
          
          socket.on('disconnect', () => {
            console.log(`Disconnected from server ${server.id}`);
            delete this.connections[server.id];
            this.checkLeadership();
          });
          
          socket.on('state-update', (data) => {
            if (!this.isLeader) {
              this.lastStateUpdate = data;
              this.emit('state-update', data);
            }
          });
          
          socket.on('connect_error', () => {
            console.log(`Failed to connect to server ${server.id}`);
          });
        } catch (err) {
          console.error(`Error connecting to server ${server.id}:`, err);
        }
      }
    });
  }
  
  /**
   * Start sending heartbeats to other servers
   */
  startHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }
    
    this.heartbeatTimer = setInterval(() => {
      // Update our own heartbeat timestamp first
      this.lastHeartbeats[this.serverId] = Date.now();
      
      // Log heartbeats for debugging
      console.log(`Server ${this.serverId} sending heartbeats to ${Object.keys(this.connections).length} connected servers`);
      
      Object.values(this.connections).forEach(socket => {
        if (socket.connected) {
          socket.emit('heartbeat', { 
            serverId: this.serverId, 
            timestamp: Date.now(),
            isLeader: this.isLeader
          });
        }
      });
    }, this.heartbeatInterval);
  }
  
  /**
   * Start monitoring heartbeats from other servers
   */
  startMonitoring() {
    if (this.monitoringTimer) {
      clearInterval(this.monitoringTimer);
    }
    
    this.monitoringTimer = setInterval(() => {
      const now = Date.now();
      
      // Check if leader is still alive
      if (this.leaderId !== null && this.leaderId !== this.serverId) {
        const lastHeartbeat = this.lastHeartbeats[this.leaderId];
        if (lastHeartbeat === 0 || (now - lastHeartbeat > this.heartbeatTimeout)) {
          console.log(`Leader ${this.leaderId} timeout detected by server ${this.serverId}. Starting election.`);
          this.checkLeadership();
        }
      }
      
      // Periodically run leadership check
      //this.checkLeadership();
    }, this.heartbeatInterval);
  }
  
  /**
   * Run the leadership election algorithm (lowest ID wins)
   */
  checkLeadership() {
    // Get IDs of active servers (including self)
    const activeServerIds = [this.serverId];
    
    // Add connected servers with proper connection validation
    Object.keys(this.connections).forEach(id => {
      const socket = this.connections[id];
      // Make sure we're only considering properly connected sockets
      if (socket && socket.connected) {
        activeServerIds.push(parseInt(id));
      }
    });
  
    // Only log when there's a change or during initialization
    if (!this.lastActiveServerIds || 
        JSON.stringify(activeServerIds) !== JSON.stringify(this.lastActiveServerIds)) {
      console.log(`Active servers: ${activeServerIds.join(', ')}`);
      this.lastActiveServerIds = [...activeServerIds];
    }
    
    // The server with lowest ID becomes leader
    const newLeaderId = Math.min(...activeServerIds);
    const wasLeader = this.isLeader;
    
    this.isLeader = (newLeaderId === this.serverId);
    this.leaderId = newLeaderId;
    
    // If leadership status changed, emit events
    if (wasLeader !== this.isLeader) {
      if (this.isLeader) {
        console.log(`Server ${this.serverId} became leader`);
        this.emit('became-leader');
      } else {
        console.log(`Server ${this.serverId} is no longer leader`);
        this.emit('stepped-down');
      }
    }
  }
  
  /**
   * Broadcast complete game state from leader to followers
   * This allows followers to take over seamlessly if the leader fails
   */
  broadcastFullGameState(rooms) {
    if (!this.isLeader) return false;
    
    // Add sequence number for ordering
    const stateUpdate = {
      action: 'fullStateSync',
      sequence: Date.now(),
      rooms: {}
    };
    
    // Only send active rooms with essential game state
    Object.keys(rooms).forEach(roomCode => {
      stateUpdate.rooms[roomCode] = {
        gameState: rooms[roomCode].gameState,
        lastActivity: rooms[roomCode].lastActivity,
        createdAt: rooms[roomCode].createdAt
      };
    });
    
    // Broadcast to all connected followers
    Object.values(this.connections).forEach(socket => {
      if (socket.connected) {
        socket.emit('state-update', stateUpdate);
      }
    });
    
    return true;
  }
  
  /**
   * Broadcast state update to all connected followers
   * For simple state updates (not full state sync)
   */
  broadcastState(data) {
    if (!this.isLeader) return false;
    
    Object.values(this.connections).forEach(socket => {
      if (socket.connected) {
        socket.emit('state-update', data);
      }
    });
    
    return true;
  }
  
  /**
   * Get the current leader server ID
   */
  getLeaderId() {
    return this.leaderId;
  }
  
  /**
   * Check if this server is the leader
   */
  isLeaderServer() {
    return this.isLeader;
  }
  
  /**
   * Get the leader server configuration
   */
  getLeaderConfig() {
    return this.clusterConfig.servers.find(s => s.id === this.leaderId);
  }
  
  /**
   * Clean up resources before shutdown
   */
  shutdown() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }
    
    if (this.monitoringTimer) {
      clearInterval(this.monitoringTimer);
    }
    
    Object.values(this.connections).forEach(socket => {
      if (socket.connected) {
        socket.disconnect();
      }
    });
    
    if (this.io) {
      this.io.close();
    }
    
    console.log(`Cluster manager for server ${this.serverId} shut down`);
  }
  
  /**
   * Request a specific room's state from the leader server
   * Used when a player tries to join a room that isn't found locally on a follower
   */
  async requestRoomFromLeader(roomCode) {
    // If we're the leader, this doesn't make sense
    if (this.isLeader) {
      return { exists: false };
    }
    
    // If we don't have a leader or connection to leader, fail
    if (this.leaderId === null || !this.connections[this.leaderId] || !this.connections[this.leaderId].connected) {
      console.log(`Can't request room ${roomCode} from leader: no leader connection`);
      throw new Error('No connection to leader server');
    }
    
    // Request room from leader using a promise to handle async response
    return new Promise((resolve, reject) => {
      const socket = this.connections[this.leaderId];
      const timeout = setTimeout(() => {
        reject(new Error('Room request timed out'));
      }, 3000); // 3 second timeout
      
      console.log(`Requesting room ${roomCode} from leader (server ${this.leaderId})`);
      
      socket.emit('room-request', { roomCode }, (response) => {
        clearTimeout(timeout);
        if (response && response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response || { exists: false });
        }
      });
    });
  }
}

module.exports = ClusterManager;