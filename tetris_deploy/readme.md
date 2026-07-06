# Tetristributed — deployment

Deployment variant of [Tetristributed](../tetris_demo/readme.md) (single-server version, kept in sync with `tetris_demo`).

**Live app: https://distributed-systems-dries-projects-e525fe65.vercel.app/**

- `client/` is built and hosted on **Vercel** (production deploys from `main`; the Vercel project's root directory points at this folder). The socket server URL is read at runtime from `client/public/config.json`.
- `server/` runs on **Render** (`render-start.js` is the entry point; Render supplies `PORT`). The free tier spins down after ~15 minutes idle, so the first connection after a quiet period takes ~30-60 s while the instance wakes.
