const socketIO = require('socket.io-client');
const { EventEmitter } = require('events');

/**
 * ClusterNode implements a Raft-inspired leader election protocol
 * This node will connect to all other nodes in the cluster and participate in leader election
 */
class ClusterNode extends EventEmitter {
  constructor(nodeId, nodeConfig, allNodes) {
    super();
    this.nodeId = nodeId;
    this.config = nodeConfig;
    this.allNodes = allNodes;
    this.connections = {}; // Connections to other nodes
    this.isLeader = false;
    this.currentLeader = null;
    this.state = 'follower'; // follower, candidate, leader
    
    // Raft consensus algorithm state
    this.currentTerm = 0;
    this.votedFor = null;
    this.votesReceived = {};
    this.log = [];

    // Timers
    this.heartbeatInterval = null;
    this.electionTimeout = null;
    this.electionTimeoutBase = allNodes.electionTimeoutBase || 150;
    this.electionTimeoutRange = allNodes.electionTimeoutRange || 150;
    this.heartbeatIntervalTime = allNodes.heartbeatInterval || 50;
    
    // Game state replication
    this.gameState = {};
    this.lastApplied = 0;
  }
  
  /**
   * Start the cluster node and connect to other nodes
   */
  start() {
    console.log(`[Node ${this.nodeId}] Starting cluster node`);
    this.connectToOtherNodes();
    this.resetElectionTimeout();
    
    // Initialize server for cluster communication
    this.initializeClusterServer();
    
    return this;
  }
  
  /**
   * Initialize the server for cluster communication
   */
  initializeClusterServer() {
    const http = require('http');
    const socketIO = require('socket.io');
    
    // Create a dedicated HTTP server for inter-node communication
    this.internalServer = http.createServer();
    
    // Initialize Socket.IO for inter-node communication with CORS settings
    this.internalIO = socketIO(this.internalServer, {
      cors: {
        origin: "*",
        methods: ["GET", "POST"]
      }
    });
    
    // Set up handlers for incoming connections from other nodes
    this.internalIO.on('connection', (socket) => {
      console.log(`[Node ${this.nodeId}] [INTERNAL] Received internal connection from another node`);
      
      // Set up handlers for inter-node messages
      socket.on('requestVote', (data) => {
        console.log(`[Node ${this.nodeId}] [RAW] Received raw vote request from ${data.candidateId}`);
        this.handleVoteRequest(data);
      });
      
      socket.on('voteResponse', (data) => {
        console.log(`[Node ${this.nodeId}] [RAW] Received raw vote response from ${data.voterId}`);
        this.handleVoteResponse(data);
      });
      
      socket.on('heartbeat', this.handleHeartbeat.bind(this));
      socket.on('leaderElected', this.handleLeaderElected.bind(this));
      socket.on('leadershipAcknowledged', this.handleLeadershipAcknowledged.bind(this));
      socket.on('stateUpdate', this.handleStateUpdate.bind(this));
      socket.on('clientRequest', this.handleClientRequest.bind(this));
    });
    
    // Start listening on the internal port
    const internalPort = this.config.internalPort || 4000 + parseInt(this.nodeId.replace('node', ''));
    this.internalServer.listen(internalPort, '0.0.0.0', () => {
      console.log(`[Node ${this.nodeId}] [INTERNAL] Internal server listening on port ${internalPort}`);
    });
    
    this.emit('ready');
  }
  
  /**
   * Connect to other nodes in the cluster
   */
  connectToOtherNodes() {
    // Connect to other nodes in the cluster
    Object.keys(this.allNodes.nodes).forEach(nodeId => {
      if (nodeId !== this.nodeId) {
        const nodeInfo = this.allNodes.nodes[nodeId];
        const internalPort = nodeInfo.internalPort || 4000 + parseInt(nodeId.replace('node', ''));
        const internalAddress = `http://${nodeInfo.ip || 'localhost'}:${internalPort}`;
        
        console.log(`[Node ${this.nodeId}] [INTERNAL] Connecting to Node ${nodeId} internal server at ${internalAddress}`);
        
        try {
          const socket = socketIO(internalAddress, {
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: Infinity
          });
          
          socket.on('connect', () => {
            console.log(`[Node ${this.nodeId}] [INTERNAL] Connected to Node ${nodeId} internal server`);
            this.connections[nodeId] = socket;
            this.emit('nodeConnected', nodeId);
            
            // If we're the leader when a new node connects, announce our leadership
            if (this.isLeader) {
              console.log(`[Node ${this.nodeId}] Announcing leadership to newly connected node ${nodeId}`);
              socket.emit('leaderElected', {
                term: this.currentTerm,
                leaderId: this.nodeId
              });
            }
          });
          
          socket.on('disconnect', () => {
            console.log(`[Node ${this.nodeId}] [INTERNAL] Disconnected from Node ${nodeId} internal server`);
            this.emit('nodeDisconnected', nodeId);
            
            // If the leader disconnects, start an election after timeout
            if (this.currentLeader === nodeId && this.state !== 'leader') {
              this.resetElectionTimeout();
            }
          });
          
          socket.on('error', (error) => {
            console.error(`[Node ${this.nodeId}] [INTERNAL] Error connecting to Node ${nodeId} internal server:`, error.message);
          });
          
          socket.io.on('error', (error) => {
            console.error(`[Node ${this.nodeId}] [INTERNAL] Socket.IO error with Node ${nodeId}:`, error.message);
          });
          
        } catch (error) {
          console.error(`[Node ${this.nodeId}] [INTERNAL] Error setting up connection to Node ${nodeId}:`, error);
        }
      }
    });
  }
  
  /**
   * Reset the election timeout with a random delay
   */
  resetElectionTimeout() {
    const oldTimeout = this.electionTimeout;
    if (this.electionTimeout) {
      clearTimeout(this.electionTimeout);
    }
    
    // Use a random timeout to prevent split votes
    const timeout = this.getRandomElectionTimeout();
    
    console.log(`[Node ${this.nodeId}] [ELECTION] Setting new election timeout: ${timeout}ms, term: ${this.currentTerm}, state: ${this.state}`);
    
    this.electionTimeout = setTimeout(() => {
      // Only start election if not a leader and haven't received heartbeat
      if (this.state !== 'leader') {
        console.log(`[Node ${this.nodeId}] [ELECTION] Election timeout triggered after ${timeout}ms, starting election...`);
        this.startElection();
      }
    }, timeout);
    
    if (oldTimeout) {
      console.log(`[Node ${this.nodeId}] [ELECTION] Reset election timeout (previous timeout cleared)`);
    }
  }
  
  /**
   * Get a random election timeout duration
   */
  getRandomElectionTimeout() {
    return this.electionTimeoutBase + 
           Math.floor(Math.random() * this.electionTimeoutRange);
  }
  
  /**
   * Start sending heartbeats to other nodes (leader only)
   */
  startHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    
    console.log(`[Node ${this.nodeId}] Starting heartbeat interval at ${this.heartbeatIntervalTime}ms`);
    
    this.heartbeatInterval = setInterval(() => {
      if (this.state === 'leader') {
        this.sendHeartbeat();
      } else if (this.heartbeatInterval) {
        // If we're not a leader anymore, stop sending heartbeats
        console.log(`[Node ${this.nodeId}] Not leader anymore, stopping heartbeat interval`);
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
    }, this.heartbeatIntervalTime);
  }
  
  /**
   * Send heartbeat to all connected nodes
   */
  sendHeartbeat() {
    if (!this.isLeader) {
      console.log(`[Node ${this.nodeId}] [HEARTBEAT] Attempted to send heartbeat but not leader`);
      return;
    }
    
    let sentCount = 0;
    let failedNodes = [];
    const startTime = Date.now();
    
    Object.keys(this.connections).forEach(nodeId => {
      const socket = this.connections[nodeId];
      if (socket && socket.connected) {
        try {
          socket.emit('heartbeat', {
            term: this.currentTerm,
            leaderId: this.nodeId,
            timestamp: startTime
          });
          sentCount++;
        } catch (error) {
          failedNodes.push(nodeId);
          console.error(`[Node ${this.nodeId}] [HEARTBEAT] Error sending heartbeat to ${nodeId}:`, error);
        }
      } else {
        failedNodes.push(nodeId);
      }
    });
    
    console.log(`[Node ${this.nodeId}] [HEARTBEAT] Sent heartbeat for term ${this.currentTerm} to ${sentCount}/${Object.keys(this.connections).length} nodes at ${new Date(startTime).toISOString()}`);
    
    if (failedNodes.length > 0) {
      console.log(`[Node ${this.nodeId}] [HEARTBEAT] Failed to send heartbeat to nodes: ${failedNodes.join(', ')}`);
    }
  }
  
  /**
   * Handle heartbeat from another node
   */
  handleHeartbeat(data) {
    const receivedTime = Date.now();
    const latency = data.timestamp ? (receivedTime - data.timestamp) : 'unknown';
    
    console.log(`[Node ${this.nodeId}] [HEARTBEAT] Received from ${data.leaderId} for term ${data.term}, latency: ${latency}ms`);
    
    // If the heartbeat term is greater than or equal to our current term, update our term and acknowledge the leader
    if (data.term >= this.currentTerm) {
      const oldState = this.state;
      const wasLeader = this.isLeader;
      const oldTerm = this.currentTerm;
      
      this.currentTerm = data.term;
      this.state = 'follower';
      this.isLeader = false;
      this.votedFor = null;
      this.currentLeader = data.leaderId;
      
      // Log state change if there was one
      if (oldState !== 'follower' || wasLeader) {
        console.log(`[Node ${this.nodeId}] [STATE] Changed from ${oldState} to follower due to heartbeat from ${data.leaderId}`);
      }
      
      if (oldTerm !== data.term) {
        console.log(`[Node ${this.nodeId}] [TERM] Updated from ${oldTerm} to ${data.term} due to heartbeat from ${data.leaderId}`);
      }
      
      // Reset election timeout since we received a valid heartbeat
      this.resetElectionTimeout();
    } else {
      console.log(`[Node ${this.nodeId}] [HEARTBEAT] Ignoring from ${data.leaderId} with older term ${data.term} < ${this.currentTerm}`);
    }
  }
  
  /**
   * Start an election for a new leader
   */
  startElection() {
    if (this.state === 'leader') {
      console.log(`[Node ${this.nodeId}] [ELECTION] Already leader, no need to start election`);
      return;
    }

    console.log(`[Node ${this.nodeId}] [ELECTION] Starting election for term ${this.currentTerm + 1}`);
    
    // Increment term, vote for self, and change state to candidate
    this.currentTerm++;
    this.votedFor = this.nodeId;
    this.state = 'candidate';
    
    // Reset votes and add vote for self
    this.votesReceived = {};
    this.votesReceived[this.nodeId] = true;
    
    // Reset election timeout to prevent starting another election too soon
    this.resetElectionTimeout();
    
    // Request votes from all other nodes
    const lastLogIndex = this.log.length - 1;
    const lastLogTerm = lastLogIndex >= 0 ? this.log[lastLogIndex].term : 0;
    
    const voteRequest = {
      term: this.currentTerm,
      candidateId: this.nodeId,
      lastLogIndex: lastLogIndex,
      lastLogTerm: lastLogTerm
    };

    console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Vote request data: ${JSON.stringify(voteRequest)}`);
    console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Connected nodes: ${Object.keys(this.connections).join(', ')}`);
    
    // Send vote requests to all other nodes
    let requestsSent = 0;
    for (const nodeId in this.connections) {
      if (nodeId !== this.nodeId && this.connections[nodeId] && this.connections[nodeId].connected) {
        console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Sending vote request to node ${nodeId}`);
        this.connections[nodeId].emit('requestVote', voteRequest);
        requestsSent++;
      } else if (nodeId !== this.nodeId) {
        console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Cannot send vote request to node ${nodeId}: not connected`);
      }
    }
    
    console.log(`[Node ${this.nodeId}] [ELECTION] Sent ${requestsSent} vote requests, waiting for responses`);
    
    // If only one node, immediately become leader
    const totalNodes = Object.keys(this.allNodes.nodes).length;
    if (totalNodes === 1) {
      console.log(`[Node ${this.nodeId}] [ELECTION] I'm the only node, becoming leader immediately`);
      this.becomeLeader();
    }
  }
  
  /**
   * Handle vote request from another node
   */
  handleVoteRequest(request) {
    console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Received vote request: ${JSON.stringify(request)}`);
    console.log(`[Node ${this.nodeId}] [ELECTION] Received vote request from ${request.candidateId} for term ${request.term}, my term: ${this.currentTerm}, my state: ${this.state}, my votedFor: ${this.votedFor}`);
    
    // Implement the Raft voting logic
    let voteGranted = false;
    let reason = "";
    
    // If we're already a leader for this or a higher term, decline the vote
    if (this.state === 'leader' && this.currentTerm >= request.term) {
      reason = `already leader for term: ${this.currentTerm}`;
      console.log(`[Node ${this.nodeId}] [ELECTION] Declining vote - ${reason}`);
      if (this.connections[request.candidateId] && this.connections[request.candidateId].connected) {
        console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Sending vote rejection to ${request.candidateId}`);
        this.connections[request.candidateId].emit('voteResponse', {
          term: this.currentTerm,
          voteGranted: false,
          voterId: this.nodeId,
          reason: reason
        });
      } else {
        console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Cannot send vote response to ${request.candidateId}: not connected`);
      }
      return;
    }
    
    // If the request term is greater than our current term, update term and step down
    if (request.term > this.currentTerm) {
      console.log(`[Node ${this.nodeId}] [ELECTION] Newer term detected: ${request.term} > ${this.currentTerm}, stepping down`);
      this.currentTerm = request.term;
      this.state = 'follower';
      this.isLeader = false; // Make sure we're not leader anymore
      this.votedFor = null;
      
      // Clear heartbeat interval if we were a leader
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
    }
    
    // Grant vote if we haven't voted for this term yet
    if (request.term === this.currentTerm && 
        (this.votedFor === null || this.votedFor === request.candidateId)) {
      
      // Check if candidate's log is at least as up-to-date as ours
      const lastLogIndex = this.log.length - 1;
      const lastLogTerm = this.log.length > 0 ? this.log[lastLogIndex].term : 0;
      
      // In a full implementation, we would check log up-to-dateness here
      // For this simplified implementation, we're just granting the vote
      
      voteGranted = true;
      this.votedFor = request.candidateId;
      
      // Reset election timeout since we voted for someone
      this.resetElectionTimeout();
      console.log(`[Node ${this.nodeId}] [ELECTION] Granted vote to ${request.candidateId} for term ${request.term}`);
    } else {
      reason = `already voted for ${this.votedFor} in term ${this.currentTerm}`;
      console.log(`[Node ${this.nodeId}] [ELECTION] Declining vote - ${reason}`);
    }
    
    // Send vote response
    if (this.connections[request.candidateId] && this.connections[request.candidateId].connected) {
      console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Sending vote response to ${request.candidateId}, granted: ${voteGranted}`);
      this.connections[request.candidateId].emit('voteResponse', {
        term: this.currentTerm,
        voteGranted: voteGranted,
        voterId: this.nodeId,
        reason: reason || undefined
      });
    } else {
      console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Cannot send vote to ${request.candidateId}: not connected`);
    }
  }
  
  /**
   * Handle vote response from another node
   */
  handleVoteResponse(response) {
    console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Received vote response: ${JSON.stringify(response)}`);
    console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Current state: ${this.state}, term: ${this.currentTerm}`);
    
    // Only process vote if we're still a candidate and in the same term
    if (this.state === 'candidate' && response.term === this.currentTerm) {
      // Register the vote
      if (response.voteGranted) {
        this.votesReceived[response.voterId] = true;
      }
      
      // Count votes
      const totalNodes = Object.keys(this.allNodes.nodes).length;
      const votesNeeded = Math.floor(totalNodes / 2) + 1;
      
      // Create array of nodes that voted for us
      const votingNodes = Object.keys(this.votesReceived).join(', ');
      const votesReceived = Object.keys(this.votesReceived).length;
      
      console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Vote received from ${response.voterId}, granted: ${response.voteGranted}`);
      console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Current votes: ${JSON.stringify(this.votesReceived)}`);
      console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Total nodes: ${totalNodes}, Votes needed: ${votesNeeded}, Votes received: ${votesReceived}`);
      console.log(`[Node ${this.nodeId}] [ELECTION] Votes received: ${votesReceived}/${votesNeeded}, voters: ${votingNodes}`);
      
      if (votesReceived >= votesNeeded) {
        console.log(`[Node ${this.nodeId}] [ELECTION] Received majority of votes (${votesReceived}/${totalNodes}), becoming leader`);
        this.becomeLeader();
      } else {
        console.log(`[Node ${this.nodeId}] [ELECTION] Need ${votesNeeded - votesReceived} more votes to become leader`);
      }
    } else {
      console.log(`[Node ${this.nodeId}] [ELECTION_DEBUG] Ignoring vote response - no longer a candidate or term mismatch`);
      console.log(`[Node ${this.nodeId}] [ELECTION] Vote denied by ${response.voterId}${response.reason ? ' - ' + response.reason : ''}`);
    }
  }
  
  /**
   * Become the leader of the cluster
   */
  becomeLeader() {
    const transitionTime = new Date().toISOString();
    console.log(`[Node ${this.nodeId}] [LEADER] Becoming leader for term ${this.currentTerm} at ${transitionTime}`);
    
    // Record transition details
    const oldState = this.state;
    this.state = 'leader';
    this.isLeader = true;
    this.currentLeader = this.nodeId;
    this.acknowledgedFollowers = new Set([this.nodeId]); // Count self
    
    // Log connection status at leadership transition
    const connectedNodes = Object.keys(this.connections).filter(
      nodeId => this.connections[nodeId] && this.connections[nodeId].connected
    );
    
    console.log(`[Node ${this.nodeId}] [LEADER] Connected to ${connectedNodes.length} nodes at leader transition: ${connectedNodes.join(', ') || 'none'}`);
    
    // Clear election timeout
    if (this.electionTimeout) {
      clearTimeout(this.electionTimeout);
      this.electionTimeout = null;
      console.log(`[Node ${this.nodeId}] [LEADER] Election timeout cleared upon becoming leader`);
    }
    
    // Send an immediate heartbeat to prevent other nodes from starting elections
    this.sendHeartbeat();
    console.log(`[Node ${this.nodeId}] [LEADER] Sent immediate heartbeat as new leader`);
    
    // Announce leadership
    Object.keys(this.connections).forEach(nodeId => {
      const socket = this.connections[nodeId];
      if (socket && socket.connected) {
        socket.emit('leaderElected', {
          term: this.currentTerm,
          leaderId: this.nodeId,
          timestamp: Date.now()
        });
        console.log(`[Node ${this.nodeId}] [LEADER] Announced leadership to node ${nodeId}`);
      } else {
        console.log(`[Node ${this.nodeId}] [LEADER] Could not announce leadership to disconnected node ${nodeId}`);
      }
    });
    
    // Start sending heartbeats
    this.startHeartbeat();
    
    // Emit leader event with transition metadata
    const leaderData = {
      term: this.currentTerm,
      previousState: oldState,
      timestamp: transitionTime,
      connectedNodes: connectedNodes
    };
    console.log(`[Node ${this.nodeId}] [LEADER] Leader transition metadata: ${JSON.stringify(leaderData)}`);
    this.emit('becameLeader', leaderData);
  }
  
  /**
   * Handle leader elected announcement
   */
  handleLeaderElected(data) {
    const receivedTime = Date.now();
    const latency = data.timestamp ? (receivedTime - data.timestamp) : 'unknown';
    
    console.log(`[Node ${this.nodeId}] [LEADER] Received leader announcement from ${data.leaderId} for term ${data.term}, my term: ${this.currentTerm}, my state: ${this.state}, latency: ${latency}ms`);
    
    if (data.term >= this.currentTerm) {
      // If we were a candidate or leader, step down
      const previousState = this.state;
      const wasLeader = this.isLeader;
      
      this.currentTerm = data.term;
      this.state = 'follower';
      this.isLeader = false;
      this.currentLeader = data.leaderId;
      
      // If we were a leader, stop sending heartbeats
      if (wasLeader && this.heartbeatInterval) {
        console.log(`[Node ${this.nodeId}] [LEADER] Stepping down as leader due to announcement from ${data.leaderId} for term ${data.term}`);
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      
      if (previousState !== 'follower') {
        console.log(`[Node ${this.nodeId}] [STATE] Changed from ${previousState} to follower due to leader announcement from ${data.leaderId}`);
      }
      
      // Reset election timeout
      this.resetElectionTimeout();
      
      // Explicitly acknowledge the new leader
      if (this.connections[data.leaderId] && this.connections[data.leaderId].connected) {
        console.log(`[Node ${this.nodeId}] [LEADER] Acknowledging leadership of ${data.leaderId} for term ${data.term}`);
        this.connections[data.leaderId].emit('leadershipAcknowledged', {
          term: this.currentTerm,
          followerId: this.nodeId,
          timestamp: Date.now()
        });
      } else {
        console.log(`[Node ${this.nodeId}] [LEADER] Cannot acknowledge leader ${data.leaderId}: not connected`);
      }
      
      // Emit leader changed event
      this.emit('leaderChanged', data.leaderId);
    } else {
      console.log(`[Node ${this.nodeId}] [LEADER] Ignoring leader announcement from ${data.leaderId} with older term ${data.term} < ${this.currentTerm}`);
      
      // If we're the leader with a higher term, let them know
      if (this.isLeader && this.connections[data.leaderId] && this.connections[data.leaderId].connected) {
        console.log(`[Node ${this.nodeId}] [LEADER] Sending counter leadership claim to ${data.leaderId} with higher term ${this.currentTerm}`);
        this.connections[data.leaderId].emit('leaderElected', {
          term: this.currentTerm,
          leaderId: this.nodeId,
          timestamp: Date.now()
        });
      }
    }
  }
  
  /**
   * Handle leadership acknowledgment from followers
   */
  handleLeadershipAcknowledged(data) {
    const receivedTime = Date.now();
    const latency = data.timestamp ? (receivedTime - data.timestamp) : 'unknown';
    
    console.log(`[Node ${this.nodeId}] [LEADER] Received leadership acknowledgment from ${data.followerId} for term ${data.term}, latency: ${latency}ms`);
    
    // If we're the leader, record this acknowledgment
    if (this.state === 'leader' && this.currentTerm === data.term) {
      this.acknowledgedFollowers = this.acknowledgedFollowers || new Set();
      this.acknowledgedFollowers.add(data.followerId);
      
      const followerCount = Object.keys(this.connections).length;
      const acknowledgedCount = this.acknowledgedFollowers.size;
      const acknowledgedNodes = Array.from(this.acknowledgedFollowers).join(', ');
      
      console.log(`[Node ${this.nodeId}] [LEADER] Leadership acknowledged by ${acknowledgedCount}/${followerCount} followers: [${acknowledgedNodes}]`);
      
      // Check if we have majority acknowledgment
      const totalNodes = Object.keys(this.allNodes.nodes).length;
      const majorityNeeded = Math.floor(totalNodes / 2) + 1;
      
      if (acknowledgedCount >= majorityNeeded) {
        console.log(`[Node ${this.nodeId}] [LEADER] Received majority acknowledgment (${acknowledgedCount}/${totalNodes})`);
      }
    } else {
      console.log(`[Node ${this.nodeId}] [LEADER] Ignoring leadership acknowledgment from ${data.followerId}: not leader or term mismatch (my term: ${this.currentTerm}, msg term: ${data.term})`);
    }
  }
  
  /**
   * Replicate game state to followers (leader only)
   */
  replicateState(gameState, roomCode) {
    if (!this.isLeader) {
      console.log(`[Node ${this.nodeId}] [STATE] Replication attempted but not leader, ignoring`);
      return;
    }
    
    const replicationTime = Date.now();
    
    // Add to log
    this.log.push({
      term: this.currentTerm,
      command: { type: 'gameState', roomCode, gameState }
    });
    
    const logIndex = this.log.length - 1;
    
    console.log(`[Node ${this.nodeId}] [STATE] Replicating state for room ${roomCode} to followers (logIndex: ${logIndex}, term: ${this.currentTerm})`);
    
    // Track successful replications
    let sentCount = 0;
    let failedCount = 0;
    
    // Send to all followers
    Object.keys(this.connections).forEach(nodeId => {
      const socket = this.connections[nodeId];
      if (socket && socket.connected) {
        try {
          socket.emit('stateUpdate', {
            term: this.currentTerm,
            leaderId: this.nodeId,
            logIndex: logIndex,
            gameState: gameState,
            roomCode: roomCode,
            timestamp: replicationTime
          });
          sentCount++;
        } catch (error) {
          failedCount++;
          console.error(`[Node ${this.nodeId}] [STATE] Error replicating to ${nodeId}:`, error);
        }
      } else {
        failedCount++;
      }
    });
    
    console.log(`[Node ${this.nodeId}] [STATE] Replication sent to ${sentCount} nodes, failed for ${failedCount} nodes`);
    return logIndex;
  }
  
  /**
   * Handle state update from leader
   */
  handleStateUpdate(data) {
    const receivedTime = Date.now();
    const latency = data.timestamp ? (receivedTime - data.timestamp) : 'unknown';
    
    console.log(`[Node ${this.nodeId}] [STATE] Received state update from leader ${data.leaderId} for room ${data.roomCode} (logIndex: ${data.logIndex}, term: ${data.term}, latency: ${latency}ms)`);
    
    // If the term is valid, apply the state update
    if (data.term >= this.currentTerm) {
      // Store game state
      this.gameState[data.roomCode] = data.gameState;
      
      // Add to log if not already there
      if (data.logIndex >= this.log.length) {
        this.log.push({
          term: data.term,
          command: { type: 'gameState', roomCode: data.roomCode, gameState: data.gameState }
        });
      }
      
      // Emit state update event
      this.emit('stateUpdate', data.roomCode, data.gameState);
    }
  }
  
  /**
   * Handle client request forwarded from a follower
   */
  handleClientRequest(request) {
    if (!this.isLeader) return;
    
    // Process the request as the leader
    console.log(`[Node ${this.nodeId}] Handling forwarded client request: ${request.type}`);
    this.emit('clientRequest', request);
  }
  
  /**
   * Forward a client request to the leader
   */
  forwardToLeader(request) {
    if (this.isLeader) {
      // We are the leader, handle locally
      this.emit('clientRequest', request);
      return;
    }
    
    if (this.currentLeader && this.connections[this.currentLeader] && 
        this.connections[this.currentLeader].connected) {
      console.log(`[Node ${this.nodeId}] Forwarding request to leader: ${this.currentLeader}`);
      this.connections[this.currentLeader].emit('clientRequest', request);
    } else {
      console.log(`[Node ${this.nodeId}] Can't forward request, no leader available`);
    }
  }
  
  /**
   * Clean up resources when shutting down
   */
  shutdown() {
    console.log(`[Node ${this.nodeId}] Shutting down cluster node`);
    
    // Clear intervals
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
    }
    
    if (this.electionTimeout) {
      clearTimeout(this.electionTimeout);
    }
    
    // Close connections
    Object.keys(this.connections).forEach(nodeId => {
      if (this.connections[nodeId]) {
        this.connections[nodeId].disconnect();
      }
    });
    
    // Close internal server if it exists
    if (this.internalServer) {
      this.internalServer.close(() => {
        console.log(`[Node ${this.nodeId}] [INTERNAL] Internal server closed`);
      });
    }
  }
}

module.exports = ClusterNode;