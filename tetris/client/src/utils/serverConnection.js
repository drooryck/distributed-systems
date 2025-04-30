import { io } from 'socket.io-client';
import { EventEmitter } from 'events';
import { saveGameSession, getGameSession, clearGameSession } from './sessionStorage';

// Add this function to load the config at the top of your file
async function loadConfig() {
  try {
    // Get the current hostname - this lets it work from any address
    const currentUrl = new URL(window.location.href);
    const configPath = `${currentUrl.protocol}//${currentUrl.host}/config.json`;
    
    console.log(`Loading config from ${configPath}`);
    const response = await fetch(configPath);
    
    if (!response.ok) {
      console.warn(`Failed to load config.json: ${response.status}`);
      return null;
    }
    
    const config = await response.json();
    console.log('Successfully loaded config:', config);
    return config;
  } catch (error) {
    console.warn('Error loading config.json:', error);
    return null;
  }
}

class ServerConnectionManager extends EventEmitter {
  constructor() {
    super();
    this.serverList = [];
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
  
  async initialize(onConnectedCallback = null, onStateChangeCallback = null, serverList = null) {
    if (this.initialized) {
      return;
    }
    
    this.onConnectedCallback = onConnectedCallback;
    this.onStateChangeCallback = onStateChangeCallback;


    // Try to load server list from config.json first
    let configServers = null;
    try {
      const config = await loadConfig();
      if (config && config.client && Array.isArray(config.client.serverAddresses)) {
        configServers = config.client.serverAddresses;

        this.log(`Loaded ${configServers.length} servers from config.json`);
        // log the whole addresses

        // configServers.forEach((server, index) => {
        //   this.log(`Server ${index}: ${JSON.stringify(server)}`);
        // });

      }
    } catch (e) {
      this.log(`Error loading config: ${e.message}`);
    }
  
    try {
      // Use provided server list or default to localhost ports
      this.serverList = configServers || [
        { id: 0, host: 'localhost', port: 3001 },
        { id: 1, host: 'localhost', port: 3002 }, 
        { id: 2, host: 'localhost', port: 3003 }
      ];
      
      this.log(`Initializing connection manager with ${this.serverList.length} servers`);
      // log the whole server list
      this.serverList.forEach((server, index) => {
        this.log(`Server ${index}: ${JSON.stringify(server)}`);
      });
      
      // First try to connect to any server to find the leader
      let leaderServer = null;
      
      for (const server of this.serverList) {
        const serverUrl = `http://${server.host}:${server.port}`;
        try {
          this.log(`Checking server ${serverUrl} for leader info`);
          const socket = io(serverUrl, {
            reconnection: false,
            timeout: 5000
          });
          
          // Wait for connection or timeout
          const isConnected = await new Promise((resolve) => {
            const timeout = setTimeout(() => {
              socket.disconnect();
              resolve(false);
            }, 5000);
            
            socket.on('connect', () => {
              clearTimeout(timeout);
              resolve(true);
            });
            
            socket.on('connect_error', () => {
              clearTimeout(timeout);
              socket.disconnect();
              resolve(false);
            });
          });
          
          if (isConnected) {
            // Get leader info from this server
            const leaderInfo = await new Promise((resolve) => {
              socket.emit('checkLeader', {}, (response) => {
                if (response && response.isLeader) {
                  // This server is the leader
                  resolve({
                    id: server.id,
                    host: server.host,
                    port: server.port,
                    url: serverUrl
                  });
                } else if (response && response.leaderUrl) {
                  // Get leader info from response
                  const leaderParts = response.leaderUrl.split(':');
                  const leaderPort = parseInt(leaderParts[leaderParts.length - 1]);
                  const leaderHost = leaderParts[leaderParts.length - 2].replace(/\/\//g, '');
                  
                  resolve({
                    id: response.leaderId || 0,
                    host: leaderHost,
                    port: leaderPort,
                    url: response.leaderUrl
                  });
                } else {
                  // No leader info, use this server temporarily
                  resolve({
                    id: server.id,
                    host: server.host,
                    port: server.port,
                    url: serverUrl
                  });
                }
              });
              
              // If no response in 3 seconds, just use this server
              setTimeout(() => {
                resolve({
                  id: server.id,
                  host: server.host,
                  port: server.port,
                  url: serverUrl
                });
              }, 3000);
            });
            
            socket.disconnect();
            leaderServer = leaderInfo;
            break;
          }
        } catch (error) {
          this.log(`Error checking server ${serverUrl}: ${error.message}`);
          // Continue to next server
        }
      }
      
      // Now connect to the leader server or first server if no leader found
      if (leaderServer) {
        this.log(`Connecting to leader server at ${leaderServer.url}`);
        await this.connectToServer(leaderServer);
      } else if (this.serverList.length > 0) {
        // Try each server until one works
        for (const server of this.serverList) {
          const serverUrl = `http://${server.host}:${server.port}`;
          try {
            this.log(`Trying to connect to server ${serverUrl}`);
            await this.connectToServer({ 
              id: server.id,
              host: server.host,
              port: server.port,
              url: serverUrl
            });
            if (this.activeSocket) break;
          } catch (error) {
            this.log(`Failed to connect to ${serverUrl}: ${error.message}`);
          }
        }
      }
      
      this.initialized = true;
      
      // If we don't have a connection yet, schedule a retry
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
  
  async connectToServer(server) {
    if (!server || !server.url) {
      throw new Error('Invalid server configuration');
    }
    
    const serverUrl = new URL(server.url);
    const absoluteUrl = `http://${serverUrl.hostname}:${serverUrl.port}`;
    
    this.log(`Connecting to server at ${absoluteUrl}`);
    
    // Connect using the absolute URL (not relative)
    const socket = io(absoluteUrl, {
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 10000,
      transports: ['polling', 'websocket'] // Try polling first, then websocket
    });
    
    return new Promise((resolve, reject) => {
      
      // Set up connection timeout
      const timeout = setTimeout(() => {
        socket.disconnect();
        reject(new Error(`Connection timeout to ${server.url}`));
      }, 10000);
      
      // Handle connection
      socket.on('connect', () => {
        clearTimeout(timeout);
        this.log(`Connected to server at ${server.url}`);
        this.setActiveServer(socket, server);
        resolve(true);
      });
      
      // Handle connection error
      socket.on('connect_error', (error) => {
        clearTimeout(timeout);
        this.log(`Connection error to ${server.url}: ${error.message}`);
        reject(error);
      });
      
      // Handle disconnection
      socket.on('disconnect', (reason) => {
        this.log(`Disconnected from ${server.url}: ${reason}`);
        
        // If this was our active socket, try to reconnect
        if (this.activeSocket === socket) {
          this.activeSocket = null;
          
          // Notify about server change
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
    
    // Forward events from this socket
    this.forwardEvents(socket);
    
    // Try to rejoin a room if we have saved session
    this.attemptRoomRejoin(socket);
    
    // Call the connected callback if provided
    if (this.onConnectedCallback) {
      this.onConnectedCallback(socket);
    }
    
    // Notify about server change
    if (this.onStateChangeCallback) {
      this.onStateChangeCallback({
        type: 'connected',
        server: server.url,
      });
    }
  }
  
  scheduleReconnect() {
    // First check if our origin server is different from active leader
    const currentUrl = new URL(window.location.href);
    const currentPort = currentUrl.port;
    
    // Try to find a working server to redirect to
    this.serverList.forEach(server => {
      if (server.port.toString() !== currentPort) {
        // Try a basic ping to see if this server is alive
        fetch(`http://${server.host}:${server.port}/status`, { timeout: 2000 })
          .then(response => {
            if (response.ok) {
              // Found a working server, redirect the browser
              this.log(`Redirecting to working server: ${server.port}`);
              
              // Save that we need to rejoin
              localStorage.setItem('needs_browser_rejoin', 'true');
              
              // Redirect the browser to the new server
              window.location.href = window.location.href.replace(
                `:${currentPort}`,
                `:${server.port}`
              );
              return;
            }
          })
          .catch(() => {
            // This server is also down, try the next one
          });
      }
    });
    
    // Continue with normal reconnection if we didn't redirect
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
  
  attemptRoomRejoin(socket) {
    const session = getGameSession();
    if (session && session.roomCode) {
      this.log(`Attempting to rejoin room ${session.roomCode} as ${session.playerName}`);
      
      // Check if player was ready before disconnection
      // This is determined by looking at the readyPlayers array in localStorage if available
      let wasReady = false;
      try {
        // Try to determine if player was ready by checking local storage
        const localReadyStatus = localStorage.getItem(`player_ready_${session.socketId}`);
        if (localReadyStatus === 'true') {
          wasReady = true;
          this.log(`Player was previously ready, sending ready status in rejoin`);
        }
      } catch (e) {
        this.log(`Could not determine previous ready status: ${e.message}`);
      }
      
      socket.emit('rejoinRoom', {
        roomCode: session.roomCode,
        playerName: session.playerName,
        previousSocketId: session.socketId || this.socketId,
        wasReady: wasReady // Include ready status in rejoin request
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