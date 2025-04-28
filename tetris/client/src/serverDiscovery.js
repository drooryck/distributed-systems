import { io } from 'socket.io-client';

/**
 * Connect to the cluster of servers with automatic leader discovery
 * Attempts to connect to each server in sequence until it finds the leader
 */
export async function connectToCluster(initialUrl = null) {
  try {
    // Load cluster configuration
    const response = await fetch('/config.json');
    const config = await response.json();
    
    // Try the initial URL first (the one the user typed in browser)
    if (initialUrl) {
      try {
        console.log(`Trying to connect to initial URL: ${initialUrl}`);
        const socket = io(initialUrl, { timeout: 5000 });
        
        const result = await new Promise((resolve, reject) => {
          let timeoutId = setTimeout(() => {
            socket.disconnect();
            reject(new Error(`Connection to ${initialUrl} timed out`));
          }, 5000);
          
          socket.on('connect', () => {
            socket.emit('getLeaderInfo');
          });
          
          socket.on('leaderInfo', (info) => {
            clearTimeout(timeoutId);
            if (info.isLeader) {
              console.log(`Connected to leader at ${initialUrl}`);
              resolve({ socket, redirect: false });
            } else if (info.leaderAddress) {
              console.log(`Redirecting to leader at ${info.leaderAddress}`);
              socket.disconnect();
              resolve({ socket: null, redirect: true, redirectTo: info.leaderAddress });
            } else {
              socket.disconnect();
              reject(new Error('No leader information available'));
            }
          });
          
          socket.on('connect_error', (err) => {
            clearTimeout(timeoutId);
            socket.disconnect();
            reject(err);
          });
        });
        
        if (result.redirect) {
          return io(result.redirectTo);
        }
        
        return result.socket;
      } catch (initialUrlError) {
        console.warn('Failed to connect to initial URL:', initialUrlError);
        // Fall through to trying other servers
      }
    }
    
    // Try all configured servers in sequence
    const serverUrls = config.clusterServers || 
                       [config.serverAddress || 'http://localhost:3001'];
    
    for (const serverUrl of serverUrls) {
      try {
        console.log(`Trying to connect to ${serverUrl}`);
        const socket = io(serverUrl, { timeout: 3000 });
        
        const result = await new Promise((resolve, reject) => {
          let timeoutId = setTimeout(() => {
            socket.disconnect();
            reject(new Error(`Connection to ${serverUrl} timed out`));
          }, 3000);
          
          socket.on('connect', () => {
            socket.emit('getLeaderInfo');
          });
          
          socket.on('leaderInfo', (info) => {
            clearTimeout(timeoutId);
            if (info.isLeader) {
              console.log(`Connected to leader at ${serverUrl}`);
              resolve({ socket, redirect: false });
            } else if (info.leaderAddress) {
              console.log(`Redirecting to leader at ${info.leaderAddress}`);
              socket.disconnect();
              resolve({ socket: null, redirect: true, redirectTo: info.leaderAddress });
            } else {
              socket.disconnect();
              reject(new Error('No leader information available'));
            }
          });
          
          socket.on('connect_error', (err) => {
            clearTimeout(timeoutId);
            socket.disconnect();
            reject(err);
          });
        });
        
        if (result.redirect) {
          return io(result.redirectTo);
        }
        
        return result.socket;
      } catch (error) {
        console.warn(`Failed to connect to ${serverUrl}:`, error);
        // Continue trying next server
      }
    }
    
    throw new Error('Could not connect to any server in the cluster');
  } catch (error) {
    console.error('Server discovery failed:', error);
    throw error;
  }
}