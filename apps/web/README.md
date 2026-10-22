# Chess Engine Web

React + TypeScript + Vite frontend.

## Prerequisites

- Node 20+ and npm
- The API running on `http://127.0.0.1:8000` (see `../api/README.md`)

## Setup

```bash
npm ci        # reproducible install from package-lock.json
```

`npm install` is not used for setup: it can silently change the lockfile.

## Run

```bash
npm run dev   # http://localhost:5173
```

The dev server proxies `/api` to `http://127.0.0.1:8000` (see `vite.config.ts`),
so the browser talks to a single origin. That keeps the session cookie
first-party (`SameSite=Lax`) and means no environment variable is needed for
local development.

Set `VITE_API_BASE` only when the API is served from a different origin, in
which case that origin must also appear in the API's `CORS_ORIGINS`:

```bash
VITE_API_BASE=https://api.example.com npm run dev
```

## Scripts

```bash
npm run dev          # start dev server
npm run build        # type-check + production build
npm run typecheck    # tsc --noEmit
npm run lint         # eslint
npm run format       # prettier --write
npm run format:check # prettier --check
npm run test         # vitest watch
npm run test:run     # vitest run
```

## Layout

```
src/app/          AuthContext, RequireAuth, useAuth
src/pages/        AuthPages, Dashboard, GamePage
src/components/   Chessboard, MoveHistory, GameStatus, ui primitives
src/lib/          api-client, api-types, chess display helpers
```
