/**
 * Dashboard (WEB-009/020/021/022/023): new-game setup (mode + difficulty),
 * saved-game listing, logout (WEB-007).
 */
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../app/useAuth';
import { ApiError, api } from '../lib/api-client';
import type { GameMode, GameResponse } from '../lib/api-types';

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [games, setGames] = useState<GameResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<GameMode>('local');
  const [depth, setDepth] = useState(3);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .listGames()
      .then((list) => {
        if (!cancelled) setGames(list);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load games');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      const game = await api.createGame({ mode });
      // Difficulty is per-move budget; stored on the play page for engine calls.
      navigate(`/games/${game.id}`, { state: { depth } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create game');
    } finally {
      setCreating(false);
    }
  }

  async function handleLogout() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <main>
      <header className="dashboard-header">
        <h1>Chess</h1>
        <p>
          Signed in as <strong>{user?.email}</strong>{' '}
          <button type="button" onClick={handleLogout}>
            Log out
          </button>
        </p>
      </header>

      <section aria-label="new game">
        <h2>New game</h2>
        <label>
          Mode
          <select value={mode} onChange={(e) => setMode(e.target.value as GameMode)}>
            <option value="local">Local two-player</option>
            <option value="computer">Player vs computer</option>
          </select>
        </label>
        {mode === 'computer' && (
          <label>
            Engine depth (1–5)
            <input
              type="number"
              min={1}
              max={5}
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
            />
          </label>
        )}
        <button type="button" onClick={handleCreate} disabled={creating}>
          {creating ? 'Creating…' : 'Start game'}
        </button>
      </section>

      <section aria-label="saved games">
        <h2>Your games</h2>
        {loading && <p role="status">Loading games…</p>}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {!loading && !error && games.length === 0 && <p>No games yet — start one above.</p>}
        <ul>
          {games.map((g) => (
            <li key={g.id}>
              <Link to={`/games/${g.id}`}>
                Game #{g.id} — {g.mode} — {g.status} ({g.moves.length} moves)
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
