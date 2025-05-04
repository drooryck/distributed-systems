# Tetristributed

A distributed co-op multiplayer Tetris implementation with real-time gameplay and fault tolerance.

## Project Overview

Tetris is a universally recognized and deceptively simple game. We aimed to build a co-op multiplayer version over the network that we could deploy to production. In our version, multiple sets of tetrominoes fall simultaneously, and each player controls one of the sets of blocks on his/her local machine.The project forced us to tackle many distributed systems challenges, from the client synchronization issues of sharing real-time game state under network latency to the reliability issues of 2-fault-tolerance under server failures. We leverage the model of leader-follower server communication in a cluster with a simple heartbeat election protocol for failover, and use a methodical fine grained board locking system to handle concurrency. We built our app on fullstack JavaScript, using React for frontend UI and Node for the webserver, and enhanced Socket.IO for cluster communication. Our app supports up to four players and up to 10 concurrent games.

## Architecture

Explanation of the server architecture in 3 diagrams. To read more, please see the write-up and poster for our project in the readme folder.

![Cluster](readme/clusterflow_dead_tetris.png)
![Frontend](readme/frontend_tetris.png)
![Server](readme/serverflow_tetris.png)

## Key Game Features

- Nintendo Rotation System
- Multiplayer mechanics (shared board, collision detection)
- Scoring system
- Visual effects and animations

## Technical Implementation

### Server-Side
- Express/Node.js backend
- Socket.IO for real-time communication
- Leader election algorithm
- State replication between servers

### Client-Side
- React frontend
- Canvas-based rendering
- Reconnection handling

See more in our write-up.


## Getting Started

### Prerequisites
- Node.js v14+ 
- npm or yarn

### Installation
```bash
# Clone repository
git clone git@github.com:drooryck/distributed-systems.git

# Install server dependencies
cd tetristributed/server
npm install

# Install client dependencies
cd ../client
npm install

# put the right local machine ip for the wifi interface into server/cluster-config.json
ipconfig getifaddr en0

# spin up the cluster
cd ../server 
./run-cluster.sh

# connect to <local_ip>:3000, and enjoy!

