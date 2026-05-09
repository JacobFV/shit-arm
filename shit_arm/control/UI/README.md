# shit-arm React UI

Vite + React control panel for the arm WebSocket server.

```bash
npm run ui
```

The app connects to `ws://127.0.0.1:8765/ws` by default. Override it with:

```bash
VITE_WS_URL=ws://127.0.0.1:8765/ws npm run ui
```

Useful root workspace commands:

```bash
npm run ui
npm run build:ui
npm run lint:ui
```
