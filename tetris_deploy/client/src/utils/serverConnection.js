import { io } from 'socket.io-client';
import { EventEmitter } from 'events';

class ServerConnectionManager extends EventEmitter {
  constructor() {
    super();
    this.activeSocket = null;
    this.socketId = null;
    
    // Configuration
    this.debug = true;
    this.autoReconnect = true;
    this.reconnectInterval = 2000;
    
    // Status tracking
    this.initialized = false;
    this.reconnectTimer = null;
  }
  
  log(message) {
    if (this.debug) {
      console.log(`[ServerManager] ${message}`);
    }
  }
  
  async initialize(onConnectedCallback = null, onStateChangeCallback = null) {
    if (this.initialized) return;
    this.onConnectedCallback = onConnectedCallback;
    this.onStateChangeCallback = onStateChangeCallback;

    let target;
    try {
      // First try to get config from config.json
      const response = await fetch('/config.json');
      const config = await response.json();
      
      // If we're running locally (on localhost:3000), use localhost:3001
      if (window.location.hostname === 'localhost') {
        target = 'http://localhost:3001';
      } else {
        // Otherwise use the configured server (for Vercel + Render deployment)
        target = config.client.serverAddresses[0];
      }
      
      this.log(`Connecting to server at ${target}`);
    } catch (error) {
      console.error('Failed to load config:', error);
      target = 'http://localhost:3001'; // fallback for development
    }
    
    const socket = io(target, {
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 10000,
      transports: ['websocket', 'polling']
    });

    socket.on('connect', () => {
      this.setActiveServer(socket, { url: target });
    });

    socket.on('connect_error', () => {
      if (this.onStateChangeCallback) {
        this.onStateChangeCallback({ type: 'disconnected' });
      }
    });

    socket.on('disconnect', () => {
      if (this.onStateChangeCallback) {
        this.onStateChangeCallback({ type: 'disconnected' });
      }
      if (this.autoReconnect) {
        this.scheduleReconnect();
      }
    });

    this.initialized = true;
  }
  
  // Single-server mode: no multi-server probing/connecting
  
  setActiveServer(socket, server) {
    this.activeSocket = socket;
    this.socketId = socket.id;
    
    // Forward events from this socket
    this.forwardEvents(socket);
    
    // Call the connected callback if provided
    if (this.onConnectedCallback) {
      this.onConnectedCallback(socket);
    }
    
    // Notify about server connection
    if (this.onStateChangeCallback) {
      this.onStateChangeCallback({ type: 'connected', server: server.url });
    }
  }
  
  scheduleReconnect() {
    // Single-server mode: just re-initialize after a delay
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    
    this.reconnectTimer = setTimeout(async () => {
      this.log('Attempting to reconnect...');
      await this.initialize(this.onConnectedCallback, this.onStateChangeCallback);
    }, this.reconnectInterval);
  }
  
  forwardEvents(socket) {
    if (!socket) return;
    
    // Forward common events from the socket to this event emitter
    const eventsToForward = [
      'init', 'gameState', 'roomCreated', 'roomJoined', 'roomRejoined',
      'roomLeft', 'playerJoined', 'playerLeft', 'playerReady',
      'gameStarted', 'gameOver', 'error', 'disconnect'
    ];
    
    eventsToForward.forEach(eventName => {
      socket.on(eventName, (data) => {
        if (eventName === 'init' && typeof data === 'string') {
          try {
            const parsedData = JSON.parse(data);
            this.log(`Converted string to object for init event`);
            data = parsedData;
          } catch (e) {
            this.log(`Could not parse init string as JSON, creating default homescreen state`);
            data = { 
              appPhase: 'homescreen',
              socketId: socket.id,
              players: {},
              activePlayers: [],
              readyPlayers: [],
              gameInProgress: false
            };
          }
        }
        
        this.emit(eventName, data);
      });
    });
  }
  
  // Room rejoin disabled - no attemptRoomRejoin function
  
  emit(eventName, data) {
    // For non-EventEmitter events, send to server
    if (eventName !== 'newListener' && eventName !== 'removeListener') {
      if (this.activeSocket) {
        this.activeSocket.emit(eventName, data);
      } else {
        this.log(`Cannot emit ${eventName}: no active socket`);
      }
    }
    
    // Always forward all events to local listeners
    return super.emit(eventName, data);
  }
  
  getSocket() {
    return this.activeSocket;
  }
  
  getSocketId() {
    return this.socketId;
  }
  
  disconnect() {
    if (this.activeSocket) {
      this.activeSocket.disconnect();
    }
    
    this.activeSocket = null;
    this.initialized = false;
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

// Create a singleton instance
const serverManager = new ServerConnectionManager();
export default serverManager;