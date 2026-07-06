import { io } from 'socket.io-client';
import { EventEmitter } from 'events';
import { getGameSession } from './sessionStorage';

// Load the server URL from public/config.json; fall back to localhost:3001.
async function loadServerUrl() {
  try {
    const response = await fetch('/config.json');
    if (response.ok) {
      const config = await response.json();
      if (config && config.serverUrl) {
        return config.serverUrl;
      }
    }
  } catch (error) {
    console.warn('Could not load config.json, using default server address:', error);
  }
  return `http://${window.location.hostname}:3001`;
}

// Events the server emits that the app listens for.
const FORWARDED_EVENTS = [
  'init', 'gameState', 'roomCreated', 'roomJoined', 'roomRejoined',
  'roomLeft', 'playerJoined', 'playerLeft', 'playerRejoined', 'playerReady',
  'hostAssigned', 'gameOver', 'error', 'disconnect'
];

class ServerConnectionManager extends EventEmitter {
  constructor() {
    super();
    this.activeSocket = null;
    this.socketId = null;
    this.serverUrl = null;
    this.initialized = false;
    this.debug = false;
  }

  log(message) {
    if (this.debug) {
      console.log(`[ServerManager] ${message}`);
    }
  }

  async initialize(onConnectedCallback = null, onStateChangeCallback = null) {
    if (this.initialized) {
      return;
    }
    this.initialized = true;

    this.onConnectedCallback = onConnectedCallback;
    this.onStateChangeCallback = onStateChangeCallback;
    this.serverUrl = await loadServerUrl();

    this.log(`Connecting to server at ${this.serverUrl}`);

    const socket = io(this.serverUrl, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 20000,
      transports: ['websocket', 'polling']
    });
    this.activeSocket = socket;

    FORWARDED_EVENTS.forEach(eventName => {
      socket.on(eventName, (data) => super.emit(eventName, data));
    });

    socket.on('connect', () => {
      this.log(`Connected with socket id ${socket.id}`);
      this.socketId = socket.id;

      // If we have a saved session (page refresh or reconnect), rejoin the room
      this.attemptRoomRejoin(socket);

      if (this.onConnectedCallback) {
        this.onConnectedCallback(socket);
      }
      if (this.onStateChangeCallback) {
        this.onStateChangeCallback({ type: 'connected', server: this.serverUrl });
      }
    });

    socket.on('disconnect', (reason) => {
      this.log(`Disconnected: ${reason}`);
      if (this.onStateChangeCallback) {
        this.onStateChangeCallback({
          type: 'disconnected',
          message: `Disconnected from server: ${reason}`
        });
      }
    });
  }

  attemptRoomRejoin(socket) {
    const session = getGameSession();
    if (session && session.roomCode) {
      this.log(`Attempting to rejoin room ${session.roomCode} as ${session.playerName}`);
      socket.emit('rejoinRoom', {
        roomCode: session.roomCode,
        playerName: session.playerName,
        previousSocketId: session.socketId
      });
    }
  }

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
  }
}

// Create a singleton instance
const serverManager = new ServerConnectionManager();
export default serverManager;
