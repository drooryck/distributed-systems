import { io } from 'socket.io-client';
import { EventEmitter } from 'events';
import { getGameSession } from './sessionStorage';

// Load the cluster server list from public/config.json.
async function loadConfig() {
  try {
    const currentUrl = new URL(window.location.href);
    const configPath = `${currentUrl.protocol}//${currentUrl.host}/config.json`;
    const response = await fetch(configPath);
    if (!response.ok) {
      console.warn(`Failed to load config.json: ${response.status}`);
      return null;
    }
    return await response.json();
  } catch (error) {
    console.warn('Error loading config.json:', error);
    return null;
  }
}

// Events the server emits that the app listens for.
const FORWARDED_EVENTS = [
  'init', 'gameState', 'roomCreated', 'roomJoined', 'roomRejoined',
  'roomLeft', 'playerJoined', 'playerLeft', 'playerRejoined', 'playerReady',
  'hostAssigned', 'gameOver', 'error', 'disconnect'
];

/**
 * Connection manager for the three-server cluster.
 *
 * Discovery: probe the configured servers and connect to whichever reports
 * itself as the leader (via the checkLeader ack).
 *
 * Failover: if the connection drops, ping the other servers' /status
 * endpoints; when one answers, redirect the whole browser to it. The page
 * reload lands on the new leader (followers 303-redirect page loads), and on
 * reconnect the saved session in localStorage drives an automatic rejoinRoom.
 */
class ServerConnectionManager extends EventEmitter {
  constructor() {
    super();
    this.serverList = [];
    this.activeSocket = null;
    this.socketId = null;

    this.debug = false;
    this.autoReconnect = true;
    this.reconnectInterval = 2000;

    this.initialized = false;
    this.reconnectTimer = null;
    this.redirecting = false;
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

    // Load the server list from config.json, defaulting to localhost
    const config = await loadConfig();
    this.serverList = (config && config.client && config.client.serverAddresses) || [
      { id: 0, host: 'localhost', port: 3001 },
      { id: 1, host: 'localhost', port: 3002 },
      { id: 2, host: 'localhost', port: 3003 }
    ];
    if (config && config.client && config.client.reconnectInterval) {
      this.reconnectInterval = config.client.reconnectInterval;
    }
    if (config && config.client && config.client.debug) {
      this.debug = true;
    }

    this.log(`Initializing with ${this.serverList.length} servers`);

    try {
      const leaderServer = await this.findLeader();

      if (leaderServer) {
        this.log(`Connecting to leader server at ${leaderServer.url}`);
        await this.connectToServer(leaderServer);
      } else {
        // No leader found: try each server in order until one accepts
        for (const server of this.serverList) {
          try {
            await this.connectToServer({
              ...server,
              url: `http://${server.host}:${server.port}`
            });
            if (this.activeSocket) break;
          } catch (error) {
            this.log(`Failed to connect to ${server.host}:${server.port}: ${error.message}`);
          }
        }
      }

      if (!this.activeSocket && this.autoReconnect) {
        this.scheduleReconnect();
      }
    } catch (error) {
      this.log(`Initialization error: ${error.message}`);
      if (this.autoReconnect) {
        this.scheduleReconnect();
      }
    }
  }

  // Probe each configured server and return the first that reports leadership.
  async findLeader() {
    for (const server of this.serverList) {
      const serverUrl = `http://${server.host}:${server.port}`;
      const probe = io(serverUrl, { reconnection: false, timeout: 4000 });

      const isLeader = await new Promise((resolve) => {
        const timeout = setTimeout(() => resolve(null), 4000);

        probe.on('connect', () => {
          probe.emit('checkLeader', {}, (response) => {
            clearTimeout(timeout);
            resolve(Boolean(response && response.isLeader));
          });
        });

        probe.on('connect_error', () => {
          clearTimeout(timeout);
          resolve(null);
        });
      });

      probe.disconnect();

      if (isLeader) {
        return { ...server, url: serverUrl };
      }
    }
    return null;
  }

  async connectToServer(server) {
    if (!server || !server.url) {
      throw new Error('Invalid server configuration');
    }

    this.log(`Connecting to server at ${server.url}`);

    const socket = io(server.url, {
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 10000,
      transports: ['polling', 'websocket']
    });

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        socket.disconnect();
        reject(new Error(`Connection timeout to ${server.url}`));
      }, 10000);

      socket.on('connect', () => {
        clearTimeout(timeout);
        this.log(`Connected to server at ${server.url}`);
        this.setActiveServer(socket, server);
        resolve(true);
      });

      socket.on('connect_error', (error) => {
        clearTimeout(timeout);
        reject(error);
      });

      socket.on('disconnect', (reason) => {
        this.log(`Disconnected from ${server.url}: ${reason}`);

        if (this.activeSocket === socket) {
          this.activeSocket = null;

          if (this.onStateChangeCallback) {
            this.onStateChangeCallback({
              type: 'disconnected',
              message: `Disconnected from server: ${reason}`
            });
          }

          if (this.autoReconnect && reason !== 'io client disconnect') {
            this.scheduleReconnect();
          }
        }
      });
    });
  }

  setActiveServer(socket, server) {
    this.activeSocket = socket;
    this.socketId = socket.id;

    FORWARDED_EVENTS.forEach(eventName => {
      socket.on(eventName, (data) => super.emit(eventName, data));
    });

    // After a failover redirect the page reloads; wait for the socket to
    // settle before rejoining so the server sees a stable connection.
    const needsRejoin = localStorage.getItem('needs_browser_rejoin') === 'true';
    if (needsRejoin) {
      localStorage.removeItem('needs_browser_rejoin');
      setTimeout(() => this.attemptRoomRejoin(socket), 500);
    } else {
      this.attemptRoomRejoin(socket);
    }

    if (this.onConnectedCallback) {
      this.onConnectedCallback(socket);
    }
    if (this.onStateChangeCallback) {
      this.onStateChangeCallback({ type: 'connected', server: server.url });
    }
  }

  /**
   * Called when the active connection is lost. First look for another live
   * server to redirect the browser to (leader failover); if none answers,
   * retry initialization on a timer.
   */
  async scheduleReconnect() {
    if (this.redirecting) return;

    const currentPort = new URL(window.location.href).port;

    for (const server of this.serverList) {
      if (server.port.toString() === currentPort) continue;

      try {
        const response = await fetch(`http://${server.host}:${server.port}/status`, {
          signal: AbortSignal.timeout(2000)
        });
        if (response.ok && !this.redirecting) {
          this.redirecting = true;
          this.log(`Redirecting to working server on port ${server.port}`);
          localStorage.setItem('needs_browser_rejoin', 'true');
          window.location.href = window.location.href.replace(
            `:${currentPort}`,
            `:${server.port}`
          );
          return;
        }
      } catch (error) {
        // Server is down too; try the next one
      }
    }

    // Nobody answered: retry from scratch after a delay
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.reconnectTimer = setTimeout(async () => {
      this.log('Attempting to reconnect...');
      this.initialized = false;
      await this.initialize(this.onConnectedCallback, this.onStateChangeCallback);
    }, this.reconnectInterval);
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

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

// Create a singleton instance
const serverManager = new ServerConnectionManager();
export default serverManager;
