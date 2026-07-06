/**
 * Integration tests against the real server: boots src/server.js on an
 * ephemeral port (NODE_ENV=test) and drives it with real socket.io clients.
 */
const { io: ioClient } = require('socket.io-client');
const { server, rooms } = require('../../src/server');

let serverUrl;
const clients = [];

function createClient() {
  const client = ioClient(serverUrl, { transports: ['websocket'], forceNew: true });
  clients.push(client);
  return client;
}

function waitFor(socket, event) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for '${event}'`)), 5000);
    socket.once(event, (data) => {
      clearTimeout(timer);
      resolve(data);
    });
  });
}

function connect(client) {
  return waitFor(client, 'connect');
}

beforeAll((done) => {
  if (server.listening) {
    serverUrl = `http://localhost:${server.address().port}`;
    done();
  } else {
    server.once('listening', () => {
      serverUrl = `http://localhost:${server.address().port}`;
      done();
    });
  }
});

afterEach(() => {
  while (clients.length) {
    clients.pop().disconnect();
  }
});

afterAll((done) => {
  server.close(done);
});

describe('room lifecycle', () => {
  test('creates a room and reports the creator as host', async () => {
    const host = createClient();
    await connect(host);

    host.emit('createRoom', { playerName: 'Alice' });
    const created = await waitFor(host, 'roomCreated');

    expect(created.roomCode).toMatch(/^[A-Z2-9]{6}$/);
    expect(created.gameState.appPhase).toBe('readyscreen');
    expect(created.gameState.players[host.id].isHost).toBe(true);
    expect(created.gameState.players[host.id].name).toBe('Alice');
  });

  test('second player can join and both see each other', async () => {
    const host = createClient();
    await connect(host);
    host.emit('createRoom', { playerName: 'Alice' });
    const { roomCode } = await waitFor(host, 'roomCreated');

    const guest = createClient();
    await connect(guest);
    const joinedNotice = waitFor(host, 'playerJoined');
    guest.emit('joinRoom', { roomCode, playerName: 'Bob' });
    const joined = await waitFor(guest, 'roomJoined');
    await joinedNotice;

    expect(Object.keys(joined.gameState.players)).toHaveLength(2);
    expect(joined.gameState.players[guest.id].name).toBe('Bob');
  });

  test('joining a nonexistent room errors', async () => {
    const client = createClient();
    await connect(client);
    client.emit('joinRoom', { roomCode: 'ZZZZZZ', playerName: 'Bob' });
    const err = await waitFor(client, 'error');
    expect(err.message).toBe('Room not found');
  });
});

describe('game flow', () => {
  async function startTwoPlayerGame() {
    const host = createClient();
    await connect(host);
    host.emit('createRoom', { playerName: 'Alice' });
    const { roomCode } = await waitFor(host, 'roomCreated');

    const guest = createClient();
    await connect(guest);
    guest.emit('joinRoom', { roomCode, playerName: 'Bob' });
    await waitFor(guest, 'roomJoined');

    host.emit('ready');
    await waitFor(host, 'playerReady');
    guest.emit('ready');
    await waitFor(guest, 'playerReady');

    host.emit('startGame');

    // Wait until the game loop broadcasts a playing state
    let state;
    do {
      state = await waitFor(host, 'gameState');
    } while (state.appPhase !== 'playing');

    return { host, guest, roomCode, state };
  }

  test('host can start the game once players are ready', async () => {
    const { state, roomCode } = await startTwoPlayerGame();
    expect(state.appPhase).toBe('playing');
    // Two-player board is 14 columns wide
    expect(state.board[0]).toHaveLength(14);
    expect(rooms[roomCode].gameState.gameInProgress).toBe(true);
  });

  test('non-host cannot start the game', async () => {
    const host = createClient();
    await connect(host);
    host.emit('createRoom', { playerName: 'Alice' });
    const { roomCode } = await waitFor(host, 'roomCreated');

    const guest = createClient();
    await connect(guest);
    guest.emit('joinRoom', { roomCode, playerName: 'Bob' });
    await waitFor(guest, 'roomJoined');

    guest.emit('startGame');
    const err = await waitFor(guest, 'error');
    expect(err.message).toBe('Only the host can start the game');
  });

  test('player actions move the piece', async () => {
    const { host, roomCode } = await startTwoPlayerGame();

    const before = rooms[roomCode].gameState.players[host.id].x;
    host.emit('playerAction', { type: 'moveLeft' });

    // Wait for the action to be applied
    await new Promise(resolve => setTimeout(resolve, 100));
    expect(rooms[roomCode].gameState.players[host.id].x).toBe(before - 1);
  });

  test('joining mid-game is rejected', async () => {
    const { roomCode } = await startTwoPlayerGame();

    const late = createClient();
    await connect(late);
    late.emit('joinRoom', { roomCode, playerName: 'Carol' });
    const err = await waitFor(late, 'error');
    expect(err.message).toBe('Game already in progress');
  });
});

describe('disconnect and rejoin', () => {
  test('mid-game disconnect parks the player for rejoin, and rejoin restores their score', async () => {
    const host = createClient();
    await connect(host);
    host.emit('createRoom', { playerName: 'Alice' });
    const { roomCode } = await waitFor(host, 'roomCreated');

    const guest = createClient();
    await connect(guest);
    guest.emit('joinRoom', { roomCode, playerName: 'Bob' });
    await waitFor(guest, 'roomJoined');

    host.emit('ready');
    await waitFor(host, 'playerReady');
    guest.emit('ready');
    await waitFor(guest, 'playerReady');
    host.emit('startGame');
    let state;
    do {
      state = await waitFor(host, 'gameState');
    } while (state.appPhase !== 'playing');

    // Give the guest a score, then disconnect them mid-game
    const guestId = guest.id;
    rooms[roomCode].gameState.players[guestId].score = 300;
    const leftNotice = waitFor(host, 'playerLeft');
    guest.disconnect();
    await leftNotice;

    expect(rooms[roomCode].gameState.players[guestId]).toBeUndefined();
    const saved = Object.values(rooms[roomCode].gameState.disconnectedPlayers);
    expect(saved).toHaveLength(1);
    expect(saved[0].score).toBe(300);
    expect(saved[0].name).toBe('Bob');

    // Rejoin with the saved session info
    const rejoiner = createClient();
    await connect(rejoiner);
    rejoiner.emit('rejoinRoom', { roomCode, playerName: 'Bob', previousSocketId: guestId });
    const rejoined = await waitFor(rejoiner, 'roomRejoined');

    expect(rejoined.gameState.players[rejoiner.id].score).toBe(300);
    expect(rejoined.gameState.players[rejoiner.id].name).toBe('Bob');
    expect(Object.keys(rooms[roomCode].gameState.disconnectedPlayers)).toHaveLength(0);
  });

  test('unknown player cannot rejoin into a running game', async () => {
    const host = createClient();
    await connect(host);
    host.emit('createRoom', { playerName: 'Alice' });
    const { roomCode } = await waitFor(host, 'roomCreated');

    host.emit('ready');
    await waitFor(host, 'playerReady');
    host.emit('startGame');
    let state;
    do {
      state = await waitFor(host, 'gameState');
    } while (state.appPhase !== 'playing');

    const stranger = createClient();
    await connect(stranger);
    stranger.emit('rejoinRoom', { roomCode, playerName: 'Mallory', previousSocketId: 'nope' });
    const err = await waitFor(stranger, 'error');
    expect(err.message).toBe('Game already in progress');
  });

  test('lobby rejoin after refresh transfers the player to the new socket', async () => {
    // Two players so the room survives when one disconnects
    const a = createClient();
    await connect(a);
    a.emit('createRoom', { playerName: 'Alice' });
    const { roomCode } = await waitFor(a, 'roomCreated');
    const b = createClient();
    await connect(b);
    b.emit('joinRoom', { roomCode, playerName: 'Bob' });
    await waitFor(b, 'roomJoined');

    const aOldId = a.id;
    a.disconnect();
    await new Promise(resolve => setTimeout(resolve, 100));

    const back = createClient();
    await connect(back);
    back.emit('rejoinRoom', { roomCode, playerName: 'Alice', previousSocketId: aOldId });
    const rejoined = await waitFor(back, 'roomRejoined');
    expect(rejoined.gameState.players[back.id].name).toBe('Alice');
    expect(rejoined.gameState.players[aOldId]).toBeUndefined();
  });
});
