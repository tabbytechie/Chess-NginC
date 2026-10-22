/**
 * Dashboard (WEB-009/020/021/022/023): new-game setup (mode + side + difficulty),
 * saved-game listing, logout (WEB-007).
 * Phase 3: the new-game flow is a real choice — side (white/black/random) and
 * engine level (easy/medium/hard) — sent to `POST /games`. The game list uses
 * the paginated summary DTO (no per-row move fetches) with a load-more control,
 * and the record comes from `GET /stats` instead of hardcoded progressions.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';

import { useAuth } from '../app/useAuth';
import { ApiError, api } from '../lib/api-client';
import type {
  EngineLevel,
  GameMode,
  GameSummaryResponse,
  NewGameColor,
  StatsResponse,
} from '../lib/api-types';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';

const MODE_LABELS: Record<GameMode, string> = {
  local: 'Local Two-Player',
  computer: 'Player vs Computer',
};

const MODE_META: Record<GameMode, { emoji: string; desc: string }> = {
  computer: { emoji: '🤖', desc: 'Battle the engine' },
  local: { emoji: '👥', desc: 'Pass & play with a friend' },
};

const LEVEL_META: Record<EngineLevel, { label: string; emoji: string; blurb: string }> = {
  easy: { label: 'Easy', emoji: '🌱', blurb: 'Chill vibes' },
  medium: { label: 'Medium', emoji: '🔥', blurb: 'Spicy' },
  hard: { label: 'Hard', emoji: '👹', blurb: 'No mercy' },
};

const COLOR_OPTIONS: { value: NewGameColor; label: string; emoji: string }[] = [
  { value: 'white', label: 'White', emoji: '♔' },
  { value: 'black', label: 'Black', emoji: '♚' },
  { value: 'random', label: 'Random', emoji: '🎲' },
];

const PAGE_SIZE = 20;

/** Fold the per-mode record into one aggregate for the header chips. */
function aggregate(stats: StatsResponse | null) {
  const acc = { wins: 0, losses: 0, draws: 0, finished: 0, total: 0 };
  if (!stats) return acc;
  for (const mode of Object.values(stats.by_mode)) {
    acc.wins += mode.wins;
    acc.losses += mode.losses;
    acc.draws += mode.draws;
    acc.finished += mode.finished;
    acc.total += mode.total;
  }
  return acc;
}

export default function Dashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [games, setGames] = useState<GameSummaryResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<GameMode>('computer');
  const [color, setColor] = useState<NewGameColor>('white');
  const [level, setLevel] = useState<EngineLevel>('medium');
  const [creating, setCreating] = useState(false);

  const record = aggregate(stats);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listGames({ limit: PAGE_SIZE, offset: 0 }), api.stats()])
      .then(([list, s]) => {
        if (cancelled) return;
        setGames(list.items);
        setTotal(list.total);
        setStats(s);
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

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    try {
      const list = await api.listGames({ limit: PAGE_SIZE, offset: games.length });
      setGames((prev) => [...prev, ...list.items]);
      setTotal(list.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load more games');
    } finally {
      setLoadingMore(false);
    }
  }, [games.length]);

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      const game = await api.createGame({ mode, player_color: color, engine_level: level });
      navigate(`/games/${game.id}`);
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

  const canLoadMore = games.length < total;

  return (
    <main className="flex-1 w-full max-w-5xl px-4 py-6">
      <motion.header
        className="hero-card mb-2xl"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <span className="hero-kicker">⚡ Season 1 · live now</span>
        <h1 className="hero-title">Chess NginC</h1>
        <p className="hero-sub">Outsmart the bot, stack wins, flex badges. Your arena awaits.</p>
        <div className="quick-start-actions">
          <Button variant="primary" onClick={handleCreate} disabled={creating}>
            {creating ? 'Summoning board…' : '▶ Quick play'}
          </Button>
          <Button variant="ghost" onClick={handleLogout}>
            Log out
          </Button>
        </div>
        <div className="stat-row" aria-label="player stats">
          <span className="stat-chip">
            🏆 <b>{record.wins}</b> wins
          </span>
          <span className="stat-chip">
            💀 <b>{record.losses}</b> losses
          </span>
          <span className="stat-chip">
            🤝 <b>{record.draws}</b> draws
          </span>
          <span className="stat-chip">
            🎮 <b>{record.total}</b> games
          </span>
        </div>
      </motion.header>

      <div className="dashboard-grid">
        <Card>
          <h2 className="text-xl font-bold mb-md">New game · 🎯 new battle</h2>
          <p className="u-text-sm mb-lg">
            Pick your mode{mode === 'computer' ? ', side & difficulty' : ' settings'}
          </p>
          <div className="mode-grid" role="radiogroup" aria-label="Game mode">
            {(Object.keys(MODE_LABELS) as GameMode[]).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mode === value}
                className={`mode-card ${mode === value ? 'active' : ''}`}
                onClick={() => setMode(value)}
              >
                <span className="mode-emoji" aria-hidden="true">
                  {MODE_META[value].emoji}
                </span>
                <span className="mode-name">{MODE_LABELS[value]}</span>
                <span className="mode-desc">{MODE_META[value].desc}</span>
              </button>
            ))}
          </div>

          {mode === 'computer' && (
            <>
              <p className="label mt-lg">Play as</p>
              <div className="color-grid" role="radiogroup" aria-label="Player color">
                {COLOR_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    role="radio"
                    aria-checked={color === opt.value}
                    className={`color-card ${color === opt.value ? 'active' : ''}`}
                    onClick={() => setColor(opt.value)}
                  >
                    <span aria-hidden="true">{opt.emoji}</span> {opt.label}
                  </button>
                ))}
              </div>

              <p className="label mt-lg">Bot difficulty</p>
              <div className="diff-grid" role="radiogroup" aria-label="Engine difficulty">
                {(Object.keys(LEVEL_META) as EngineLevel[]).map((value) => (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={level === value}
                    className={`diff-card ${level === value ? 'active' : ''}`}
                    onClick={() => setLevel(value)}
                  >
                    {LEVEL_META[value].emoji} {LEVEL_META[value].label}
                    <small>{LEVEL_META[value].blurb}</small>
                  </button>
                ))}
              </div>
            </>
          )}

          <Button
            variant="brand"
            onClick={handleCreate}
            disabled={creating}
            className="w-full mt-lg"
          >
            {creating
              ? 'Creating…'
              : `⚔ Start ${mode === 'computer' ? `${LEVEL_META[level].label} battle` : 'local game'}`}
          </Button>
        </Card>

        <Card>
          <h2 className="text-xl font-bold mb-md">Your Games</h2>
          {loading && (
            <p role="status" className="text-center text-ink-soft">
              Loading games…
            </p>
          )}
          {error && (
            <p role="alert" className="error text-center">
              {error}
            </p>
          )}
          {!loading && !error && games.length === 0 && (
            <div className="empty-state">
              <p>No games yet — start one above.</p>
            </div>
          )}
          {!loading && games.length > 0 && (
            <>
              <ul className="game-list">
                {games.map((g) => (
                  <li key={g.id} className="game-item">
                    <Link to={`/games/${g.id}`} className="flex items-center gap-md">
                      <span className="font-mono text-neon-pink">Game #{g.id}</span>
                      <span className="text-ink-soft text-sm">{MODE_LABELS[g.mode]}</span>
                      <span className="text-ink-soft text-sm">
                        • {g.status}
                        {g.status !== 'active' && g.result !== '*' ? ` (${g.result})` : ''}
                      </span>
                      <span className="ml-auto text-neon-green font-bold">
                        {g.move_count} moves
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              {canLoadMore && (
                <Button
                  variant="ghost"
                  onClick={() => void loadMore()}
                  disabled={loadingMore}
                  className="w-full mt-md"
                >
                  {loadingMore ? 'Loading…' : `Load more (${games.length}/${total})`}
                </Button>
              )}
            </>
          )}
        </Card>

        <Card>
          <h2 className="text-xl font-bold mb-md">Achievements</h2>
          <div className="badge-grid">
            <Badge
              name="First Move"
              desc="Play your first game"
              icon="♟️"
              unlocked={record.finished > 0}
            />
            <Badge
              name="Checkmate King"
              desc="Win by checkmate"
              icon="👑"
              unlocked={record.wins > 0}
            />
            <Badge
              name="Iron Draw"
              desc="Hold a drawn game"
              icon="🛡️"
              unlocked={record.draws > 0}
            />
            <Badge name="Grinder" desc="Finish 5 games" icon="⚡" unlocked={record.finished >= 5} />
          </div>
        </Card>
      </div>
    </main>
  );
}
