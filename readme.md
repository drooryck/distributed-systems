# Distributed Systems — CS 2620 (Spring 2025)

Coursework and final project for Harvard's CS 2620: Distributed Programming.

## Final project: Tetristributed

A distributed co-op multiplayer Tetris with real-time gameplay and 2-fault-tolerant server replication.

**[▶ Play it live](https://distributed-systems-dries-projects-e525fe65.vercel.app/)** · **[Read the full readme](tetris_demo/readme.md)** · [Write-up (PDF)](CS_2620_Final_Project_Writeup.pdf) · [Poster (PDF)](tetris_demo/readme/poster_cs262.pdf)

| Folder | What it is |
|---|---|
| [`tetris_demo/`](tetris_demo/) | Clean single-server version — canonical codebase, tests, and documentation |
| [`tetris/`](tetris/) | Three-server leader-follower cluster with heartbeat election and state replication |
| [`tetris_deploy/`](tetris_deploy/) | Deployment variant: client on Vercel, server on Render |

## Course assignments

| Folder | Assignment |
|---|---|
| [`messaging-app/`](messaging-app/) | Client-server chat app with a custom wire protocol vs. JSON |
| [`grpc-app/`](grpc-app/) | The chat app re-implemented over gRPC |
| [`logical-clocks/`](logical-clocks/) | Lamport logical clock simulation experiments |
| [`replication/`](replication/) | Persistent, 2-fault-tolerant replicated chat app |
