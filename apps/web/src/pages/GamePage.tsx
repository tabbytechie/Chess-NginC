/**
 * Game page (WEB-010..019, WEB-024/025): board, move submission, undo,
 * resign, draw-claim, resume via GET game.
 * Phase 3: in `computer` mode the engine replies inside the same move response,
 * so there is no manual "Engine move" button — the client just renders both
 * plies with a "thinking" state. Board orientation follows `player_color`; the
 * terminal banner shows the real result; captures derive from the move list.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';

import Chessboard from '../components/Chessboard';
import GameStatusBanner from '../components/GameStatus';
import MoveHistory from '../components/MoveHistory';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { ApiError, api, pgnDownloadUrl } from '../lib/api-client';
import { capturedPiecesFromMoves } from '../lib/chess';
import type { GameResponse } from '../lib/api-types';

export default function GamePage() {
  const { id } = useParams<{ id: string }>();

  const [game, setGame] = useState<GameResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const gameId = Number(id);
  const badId = !Number.isFinite(gameId);

  useEffect(() => {
    if (badId) return;
    let cancelled = false;
    api
      .getGame(gameId)
      .then((g) => {
        if (!cancelled) setGame(g);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load game');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, badId]);

  const run = useCallback(
    async (fn: (g: GameResponse) => Promise<GameResponse>) => {
      if (!game || busy) return;
      setBusy(true);
      setError(null);
      try {
        setGame(await fn(game));
        setSelected(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          // Stale version: re-fetch then surface the message (WEB-025).
          try {
            setGame(await api.getGame(gameId));
          } catch {
            /* keep existing state on refetch failure */
          }
        }
        setError(err instanceof ApiError ? err.message : 'Action failed');
      } finally {
        setBusy(false);
      }
    },
    [game, busy, gameId],
  );

  const handleMove = useCallback(
    (from: string, to: string, promotion?: string) => {
      // UCI promotion moves always carry a piece letter; the picker defaults to 'q'.
      const uci = `${from}${to}${promotion ?? ''}`;
      void run((g) => api.submitMove(gameId, { uci, expected_version: g.version }));
    },
    [run, gameId],
  );

  // Hooks must run unconditionally, so derive captures from `game?.moves`.
  const captures = useMemo(
    () =>
      game ? capturedPiecesFromMoves(game.moves) : { capturedByWhite: [], capturedByBlack: [] },
    [game],
  );

  if (badId) {
    return (
      <main>
        <p role="alert" className="error">
          Invalid game id.
        </p>
        <Link to="/">← All games</Link>
      </main>
    );
  }
  if (loading) return <p role="status">Loading game…</p>;
  if (error && !game)
    return (
      <main>
        <p role="alert" className="error">
          {error}
        </p>
        <Link to="/">Back to dashboard</Link>
      </main>
    );
  if (!game) return null;

  const inCheck = game.in_check;
  const finished = game.status !== 'active';
  const isComputer = game.mode === 'computer';
  // The engine's turn is whichever side is not the human's, only while playing.
  const awaitingEngine = isComputer && busy && !finished;
  const flipped = game.player_color === 'black';

  return (
    <motion.main
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="game-page w-full max-w-5xl px-4 py-6"
    >
      <Link to="/" className="text-neon-blue hover:text-neon-pink mb-md block">
        ← All games
      </Link>
      <h1 className="mb-sm">Game #{game.id}</h1>
      <GameStatusBanner
        status={game.status}
        inCheck={inCheck}
        result={game.result}
        winner={game.winner}
        playerColor={game.player_color}
      />
      {awaitingEngine && (
        <p role="status" aria-live="polite" className="thinking mb-md text-ink-soft">
          🤖 Engine is thinking…
        </p>
      )}
      {error && (
        <p role="alert" className="error mb-md">
          {error}
        </p>
      )}
      <div className="game-layout">
        <div className="game-main">
          <Chessboard
            fen={game.fen}
            status={game.status}
            selected={selected}
            onSelect={setSelected}
            onMove={handleMove}
            disabled={busy}
            flipped={flipped}
            lastMove={
              game.moves.length > 0
                ? {
                    from: game.moves[game.moves.length - 1].uci.slice(0, 2),
                    to: game.moves[game.moves.length - 1].uci.slice(2, 4),
                  }
                : null
            }
            inCheck={inCheck}
          />
        </div>
        <aside className="game-sidebar" aria-label="game panel">
          <Card>
            <h2 className="text-xl font-bold mb-md">Moves</h2>
            <MoveHistory moves={game.moves} />
          </Card>
          <Card className="mt-lg">
            <h2 className="text-xl font-bold mb-md">Captured</h2>
            <section aria-label="captured pieces" className="captures-section">
              <p className="label">Captured by White</p>
              <div className="captured-pieces" aria-label="captured by white">
                {captures.capturedByWhite.map((piece, idx) => (
                  <span key={idx} className="captured-piece" title={piece}>
                    {piece}
                  </span>
                ))}
                {captures.capturedByWhite.length === 0 && <span className="text-ink-faint">—</span>}
              </div>
              <p className="label mt-sm">Captured by Black</p>
              <div className="captured-pieces" aria-label="captured by black">
                {captures.capturedByBlack.map((piece, idx) => (
                  <span key={idx} className="captured-piece" title={piece}>
                    {piece}
                  </span>
                ))}
                {captures.capturedByBlack.length === 0 && <span className="text-ink-faint">—</span>}
              </div>
            </section>
          </Card>
          <div className="controls mt-lg">
            <Button
              variant="primary"
              onClick={() => void run((g) => api.undoMove(gameId, { expected_version: g.version }))}
              disabled={busy || finished || game.moves.length === 0}
              className="w-full"
            >
              Undo
            </Button>
            <Button
              variant="ghost"
              onClick={async () => {
                if (!game) return;
                setBusy(true);
                setError(null);
                try {
                  let current = game;
                  while (current.moves.length > 0) {
                    const next = await api.undoMove(gameId, {
                      expected_version: current.version,
                    });
                    if (next.moves.length >= current.moves.length) break;
                    current = next;
                  }
                  setGame(current);
                  setSelected(null);
                } catch (err) {
                  setError(err instanceof ApiError ? err.message : 'Reset failed');
                } finally {
                  setBusy(false);
                }
              }}
              disabled={busy || finished || game.moves.length === 0}
              className="w-full mt-sm"
            >
              Reset to start
            </Button>
            <Button
              variant="danger"
              onClick={() => void run(() => api.resignGame(gameId))}
              disabled={busy || finished}
              className="w-full mt-sm"
            >
              Resign
            </Button>
            <Button
              variant="brand"
              onClick={() => void run(() => api.claimDraw(gameId))}
              disabled={busy || finished}
              className="w-full mt-sm"
            >
              Claim draw
            </Button>
            <a
              className="pgn-link mt-sm block text-neon-blue hover:text-neon-pink"
              href={pgnDownloadUrl(gameId)}
            >
              ⬇ Download PGN
            </a>
          </div>
          <p className="hint mt-lg text-center text-xs text-ink-soft">
            {isComputer
              ? 'Play your move; the engine replies in the same step.'
              : 'Click a piece, then its destination. Promotions ask which piece.'}
          </p>
        </aside>
      </div>
    </motion.main>
  );
}
