/**
 * Post-game review (REVIEW-003/004/006/007/008/009): every ply classified by
 * Stockfish (brilliant → blunder), the engine's suggested improvement, a
 * coaching line, the evaluation graph and a per-move board replay.
 *
 * Data comes from GET /games/:id/review when a review is stored, otherwise the
 * page triggers POST (one engine pass) and shows progress. The board is a
 * read-only replay: no move submission lives here.
 *
 * The replay is a guided tour: it opens on the first move, and the navigation
 * strip, the arrow keys and the move list all walk the same recorded plies while
 * each position names its opening, its engine win expectancy and a spoken line.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Pause,
  Play,
  RefreshCw,
  Sparkles,
  Star,
  X,
} from 'lucide-react';

import Chessboard from '../components/Chessboard';
import CoachAssistant from '../components/CoachAssistant';
import EvalGraph from '../components/EvalGraph';
import ReviewThinking from '../components/ReviewThinking';
import VoiceToggle from '../components/VoiceToggle';
import VoicePicker, { type VoicePickerOption } from '../components/VoicePicker';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useAchievementRide } from '../app/useAchievementRide';
import { ApiError, api } from '../lib/api-client';
import type {
  AssistantLineStep,
  ReviewMoveResponse,
  ReviewResponse,
  VoiceOption,
} from '../lib/api-types';
import { narratePly } from '../lib/narration';
import {
  QUALITY_ORDER,
  formatEval,
  openingAverage,
  openingFamily,
  qualityMeta,
  uciSquares,
  winPctFor,
} from '../lib/review';
import { getPref } from '../lib/settings';
import { setVoiceSelection, speak, stopSpeaking } from '../lib/voice';

// The Review leads with an ElevenLabs free voice (Adam) as the main narrator;
// the browser engine is only the automatic fallback inside `speak()` (a 503 when
// no key is configured, or a quota/network error). This id is the first entry of
// the server's curated free-voice catalog (Adam synthesizes on the free plan).
const REVIEW_DEFAULT_VOICE_ID = 'pNInz6obpgDQGcFmaJgB'; // Adam

/** Where the tour starts: the first move, so the game is seen from its opening. */
function initialPly(data: ReviewResponse): number | null {
  return data.moves[0]?.ply ?? null;
}

type CursorMove = 'first' | 'prev' | 'next' | 'last';

/** Arrow/home/end keys that walk the tour, mapped to the same verbs as the strip. */
const NAV_KEYS: Record<string, CursorMove> = {
  ArrowLeft: 'prev',
  ArrowRight: 'next',
  Home: 'first',
  End: 'last',
};

/** Fields that swallow their own keystrokes: typing must not move the board. */
const KEY_CONSUMERS = /^(input|textarea|select|button)$/i;

function QualityBadge({ quality }: { quality: string }) {
  const meta = qualityMeta(quality);
  return (
    <span className={`quality quality-${meta.css}`} title={meta.label}>
      <span aria-hidden="true">{meta.glyph || '•'}</span>
      <span className="sr-only">{meta.label}</span>
    </span>
  );
}

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const gameId = Number(id);
  const badId = !Number.isFinite(gameId) || gameId <= 0;

  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPly, setSelectedPly] = useState<number | null>(null);
  // The coach assistant is a opt-in panel beside the review (Phase 11).
  const [coachOpen, setCoachOpen] = useState(false);
  // A walkable variation the coach surfaced, stepped through on the main board.
  const [lesson, setLesson] = useState<{
    steps: AssistantLineStep[];
    index: number;
    title: string;
  } | null>(null);
  const [lessonPlaying, setLessonPlaying] = useState(false);
  // Review narration voice: only the ElevenLabs free catalog is offered here,
  // Adam as the default main voice (the browser engine stays the fallback).
  const [elevenVoices, setElevenVoices] = useState<VoiceOption[]>([]);
  const [reviewVoiceId, setReviewVoiceId] = useState(REVIEW_DEFAULT_VOICE_ID);

  const exitLesson = useCallback(() => {
    setLesson(null);
    setLessonPlaying(false);
  }, []);

  const playLine = useCallback((steps: AssistantLineStep[], title: string) => {
    if (steps.length === 0) return;
    setLessonPlaying(false);
    setLesson({ steps, index: 0, title });
  }, []);

  const lessonGo = useCallback((where: CursorMove) => {
    setLesson((prev) => {
      if (!prev) return prev;
      const last = prev.steps.length - 1;
      const at = prev.index;
      const next =
        where === 'first' ? 0 : where === 'last' ? last : where === 'prev' ? at - 1 : at + 1;
      return { ...prev, index: Math.max(0, Math.min(last, next)) };
    });
  }, []);

  // Autoplay walks the lesson forward and stops on the final step.
  useEffect(() => {
    if (!lesson || !lessonPlaying) return;
    const last = lesson.steps.length - 1;
    if (lesson.index >= last) return;
    const timer = setTimeout(() => {
      lessonGo('next');
      if (lesson.index + 1 >= last) setLessonPlaying(false);
    }, 900);
    return () => clearTimeout(timer);
  }, [lesson, lessonPlaying, lessonGo]);

  useEffect(() => {
    if (badId) return;
    let cancelled = false;
    // A stored review is served straight from the DB; 409 means "not analysed
    // yet", which triggers the single engine pass (REVIEW-001/005).
    const fetchOrGenerate = api
      .getGameReview(gameId)
      .catch((err: unknown) =>
        err instanceof ApiError && err.status === 409
          ? api.createGameReview(gameId)
          : Promise.reject(err),
      );
    fetchOrGenerate
      .then((data) => {
        if (cancelled) return;
        setReview(data);
        setSelectedPly(initialPly(data));
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : 'Failed to load the review');
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, badId]);

  const selected: ReviewMoveResponse | null = useMemo(() => {
    if (!review) return null;
    const found = review.moves.find((m) => m.ply === selectedPly);
    return found ?? review.moves[review.moves.length - 1] ?? null;
  }, [review, selectedPly]);

  // Where the cursor sits in the recorded plies; -1 while nothing is loaded.
  const cursor = useMemo(() => {
    if (!review || selectedPly == null) return -1;
    return review.moves.findIndex((m) => m.ply === selectedPly);
  }, [review, selectedPly]);

  const goTo = useCallback(
    (where: CursorMove) => {
      if (!review || review.moves.length === 0) return;
      const last = review.moves.length - 1;
      const at = cursor === -1 ? 0 : cursor;
      const next =
        where === 'first' ? 0 : where === 'last' ? last : where === 'prev' ? at - 1 : at + 1;
      const move = review.moves[Math.max(0, Math.min(last, next))];
      if (move) setSelectedPly(move.ply);
    },
    [cursor, review],
  );

  // Arrow keys walk the tour for keyboard users; the strip does the same job for
  // everyone else. While the coach is walking a variation, they drive that instead.
  useEffect(() => {
    function onKeydown(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const where = NAV_KEYS[event.key];
      if (!where) return;
      const target = event.target as HTMLElement | null;
      if (target && KEY_CONSUMERS.test(target.tagName)) return;
      event.preventDefault();
      if (lesson) lessonGo(where);
      else goTo(where);
    }
    window.addEventListener('keydown', onKeydown);
    return () => window.removeEventListener('keydown', onKeydown);
  }, [goTo, lesson, lessonGo]);

  // A finished analysis is a milestone of its own (reviews_completed).
  useAchievementRide(review);

  // Narrate each step (REVIEW-009). The first render is deliberately silent:
  // browsers drop speech that was not preceded by a gesture, so the automatic
  // arrival at move one stays quiet and the first click or key does the talking.
  const spoken = useRef(false);
  useEffect(() => {
    if (!selected) return;
    if (!spoken.current) {
      spoken.current = true;
      return;
    }
    if (getPref('voice')) speak(narratePly(selected));
  }, [selected]);

  // Leaving the review must not leave a voice talking over the next page.
  useEffect(() => () => stopSpeaking(), []);

  // Load the free-voice catalog and seed the narrator with an ElevenLabs voice,
  // defaulting to Adam when the player has no stored preference yet. Degrades
  // quietly: an offline backend leaves the default selection, and `speak()` falls
  // back to the browser engine the moment ElevenLabs cannot serve.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [catalog, prefs] = await Promise.all([api.listVoices(), api.getVoicePrefs()]);
        if (!alive) return;
        const ids = new Set(catalog.voices.map((v) => v.id));
        const chosen = ids.has(prefs.voice_id) ? prefs.voice_id : REVIEW_DEFAULT_VOICE_ID;
        setElevenVoices(catalog.voices);
        setReviewVoiceId(chosen);
        setVoiceSelection({ engine: 'eleven', id: chosen });
      } catch {
        if (!alive) return;
        setVoiceSelection({ engine: 'eleven', id: REVIEW_DEFAULT_VOICE_ID });
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // The picker only ever yields an ElevenLabs free id; apply it to the narrator
  // now and persist it so the choice follows the account to the coach too.
  function chooseReviewVoice(id: string) {
    setReviewVoiceId(id);
    setVoiceSelection({ engine: 'eleven', id });
    void api.saveVoicePrefs({ voice_id: id }).catch(() => {
      /* optimistic: the selection still applies to this session */
    });
  }

  async function reanalyse() {
    setLoading(true);
    try {
      const data = await api.createGameReview(gameId, { force: true });
      setReview(data);
      setSelectedPly(initialPly(data));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to re-analyse');
    } finally {
      setLoading(false);
    }
  }

  if (badId) return <p role="alert">Invalid game id.</p>;

  if (loading) {
    return (
      <main id="main-content" className="review-page">
        <Card>
          <h1 className="card-title">Reviewing game…</h1>
          <ReviewThinking
            gameId={gameId}
            fens={review ? review.moves.map((m) => m.pre_fen) : undefined}
          />
        </Card>
      </main>
    );
  }

  if (error) {
    return (
      <main id="main-content" className="review-page">
        <Card>
          <h1 className="card-title">Review unavailable</h1>
          <p role="alert">{error}</p>
          <Button variant="ghost" onClick={() => navigate(-1)}>
            Back
          </Button>
        </Card>
      </main>
    );
  }

  if (!review) return null;

  if (review.status === 'failed') {
    return (
      <main id="main-content" className="review-page">
        <Card>
          <h1 className="card-title">The engine could not finish this review</h1>
          <p role="alert">{review.error ?? 'Analysis failed with an unknown error.'}</p>
          <div className="review-actions">
            <Button onClick={reanalyse}>
              <RefreshCw size={15} aria-hidden="true" />
              Try again
            </Button>
            <Button variant="ghost" onClick={() => navigate(-1)}>
              Back
            </Button>
          </div>
        </Card>
      </main>
    );
  }

  const hero = review.hero_color === 'w' ? 'White' : 'Black';
  const heroSide = review.hero_color;
  // Online games are played under /online/:id; the linking page passes that
  // route through state so "back" lands where the player came from.
  const backTo =
    (location.state as { backTo?: string } | null)?.backTo ?? `/games/${review.game_id}`;
  const heroAccuracy = review.summary.accuracy?.[review.hero_color];
  const board = selected
    ? { fen: selected.pre_fen, last: uciSquares(selected.uci) }
    : { fen: null, last: null };
  const improvementsForHero = review.improvements.filter((i) => i.color === review.hero_color);
  // Opening + expectancy for the ply on screen (REVIEW-008). The family average
  // is read over the whole game, so it does not jump around mid-opening.
  const family = openingFamily(selected?.opening_name);
  const heroPct = winPctFor(selected?.win_pct, heroSide);
  const familyPct = selected ? openingAverage(review.moves, family, heroSide) : null;
  const isFirst = cursor <= 0;
  const isLast = cursor >= review.moves.length - 1;
  // Only the ElevenLabs free voices are offered in the review; before the
  // catalog arrives, offer the default so the control is never empty.
  const reviewVoiceOptions: VoicePickerOption[] =
    elevenVoices.length > 0
      ? elevenVoices.map((v) => ({
          id: v.id,
          name: v.name,
          kind: 'eleven' as const,
          available: v.available,
        }))
      : [{ id: REVIEW_DEFAULT_VOICE_ID, name: 'Adam', kind: 'eleven' as const, available: true }];

  return (
    <main id="main-content" className="review-page">
      <div className="review-header">
        <Link to={backTo} className="btn btn-ghost btn-small">
          <ArrowLeft size={14} aria-hidden="true" />
          Back to game
        </Link>
        <Button variant="ghost" onClick={reanalyse} disabled={loading}>
          <RefreshCw size={14} aria-hidden="true" />
          Re-analyse
        </Button>
        <VoiceToggle />
        <VoicePicker
          label="Review narration voice"
          value={reviewVoiceId}
          options={reviewVoiceOptions}
          onChange={chooseReviewVoice}
        />
      </div>

      <div className="review-grid">
        <section className="review-board-col" aria-label="review board">
          <Card>
            {lesson ? (
              <>
                {lesson.steps[lesson.index] ? (
                  <Chessboard
                    fen={lesson.steps[lesson.index].fen_after}
                    status="active"
                    selected={null}
                    onSelect={() => {}}
                    onMove={() => {}}
                    disabled
                    lastMove={uciSquares(lesson.steps[lesson.index].uci)}
                  />
                ) : null}
                <div className="lesson-bar">
                  <div className="lesson-head">
                    <strong>{lesson.title}</strong>
                    <span className="u-muted">
                      Step {lesson.index + 1} of {lesson.steps.length}
                    </span>
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => setLessonPlaying((v) => !v)}
                      aria-label={lessonPlaying ? 'Pause line' : 'Play line'}
                      title={lessonPlaying ? 'Pause' : 'Play'}
                    >
                      {lessonPlaying ? (
                        <Pause size={16} aria-hidden="true" />
                      ) : (
                        <Play size={16} aria-hidden="true" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={exitLesson}
                      aria-label="Exit lesson"
                      title="Exit lesson"
                    >
                      <X size={16} aria-hidden="true" />
                    </Button>
                  </div>
                  <div className="review-nav" role="group" aria-label="lesson navigation">
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => lessonGo('first')}
                      disabled={lesson.index <= 0}
                      aria-label="First step"
                      title="First step"
                    >
                      <ChevronsLeft size={16} aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => lessonGo('prev')}
                      disabled={lesson.index <= 0}
                      aria-label="Previous step"
                      title="Previous step (Left arrow)"
                    >
                      <ChevronLeft size={16} aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => lessonGo('next')}
                      disabled={lesson.index >= lesson.steps.length - 1}
                      aria-label="Next step"
                      title="Next step (Right arrow)"
                    >
                      <ChevronRight size={16} aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => lessonGo('last')}
                      disabled={lesson.index >= lesson.steps.length - 1}
                      aria-label="Last step"
                      title="Last step"
                    >
                      <ChevronsRight size={16} aria-hidden="true" />
                    </Button>
                  </div>
                  {lesson.steps[lesson.index] && (
                    <p className="lesson-caption">
                      <span className={`review-san side-${lesson.steps[lesson.index].color}`}>
                        {lesson.steps[lesson.index].san}
                      </span>
                      <span className="u-muted">{lesson.steps[lesson.index].comment}</span>
                    </p>
                  )}
                </div>
              </>
            ) : (
              <>
                {board.fen ? (
                  <Chessboard
                    fen={board.fen}
                    status="active"
                    selected={null}
                    onSelect={() => {}}
                    onMove={() => {}}
                    disabled
                    lastMove={board.last}
                  />
                ) : (
                  <p className="u-muted">No moves to show.</p>
                )}
                {review.moves.length > 0 && (
                  <div className="review-nav" role="group" aria-label="move navigation">
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => goTo('first')}
                      disabled={isFirst}
                      aria-label="First move"
                      title="First move"
                    >
                      <ChevronsLeft size={16} aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => goTo('prev')}
                      disabled={isFirst}
                      aria-label="Previous move"
                      title="Previous move (Left arrow)"
                    >
                      <ChevronLeft size={16} aria-hidden="true" />
                    </Button>
                    <span className="review-nav-count">
                      Move {selected ? selected.ply : 0} of {review.moves.length}
                    </span>
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => goTo('next')}
                      disabled={isLast}
                      aria-label="Next move"
                      title="Next move (Right arrow)"
                    >
                      <ChevronRight size={16} aria-hidden="true" />
                    </Button>
                    <Button
                      variant="ghost"
                      className="nav-btn"
                      onClick={() => goTo('last')}
                      disabled={isLast}
                      aria-label="Last move"
                      title="Last move"
                    >
                      <ChevronsRight size={16} aria-hidden="true" />
                    </Button>
                  </div>
                )}
                {selected && (
                  <p className="review-current-move">
                    <QualityBadge quality={selected.quality} />
                    <strong>
                      {selected.color === 'w' ? 'White' : 'Black'} played {selected.san}
                    </strong>
                    <span className="u-muted">
                      {formatEval(selected.eval_cp, selected.eval_mate)} · {selected.centipawn_loss}{' '}
                      cp off best
                    </span>
                    <span className="review-explanation">{selected.explanation}</span>
                  </p>
                )}
              </>
            )}
          </Card>

          <Card>
            <h2 className="card-title">
              <BookOpen size={15} aria-hidden="true" /> Opening and odds
            </h2>
            {selected?.opening_name ? (
              <div className="review-opening">
                <p className="review-opening-line">
                  {selected.opening_eco && (
                    <span className="opening-eco">{selected.opening_eco}</span>
                  )}
                  <strong>{selected.opening_name}</strong>
                  <span className={`book-badge${selected.in_book ? ' in-book' : ''}`}>
                    {selected.in_book ? 'In book' : 'Out of book'}
                  </span>
                </p>
                {heroPct != null && (
                  <div className="review-odds">
                    <div
                      className="odds-bar"
                      role="img"
                      aria-label={`${hero} win expectancy ${heroPct} percent`}
                    >
                      <span className="odds-fill" style={{ width: `${heroPct}%` }} />
                    </div>
                    <p className="u-muted">
                      {hero}&apos;s engine win expectancy here: <strong>{heroPct}%</strong>
                    </p>
                  </div>
                )}
                {familyPct != null && (
                  <p className="u-muted">Across this opening in this game, about {familyPct}%.</p>
                )}
              </div>
            ) : (
              <p className="u-muted">
                This position is outside the theory book, so no opening is named for it.
              </p>
            )}
            <p className="u-muted review-opening-note">
              Engine expectancy for the position on the board — not a win rate copied from other
              players&rsquo; games.
            </p>
          </Card>

          <Card>
            <h2 className="card-title">Evaluation over the game</h2>
            <EvalGraph
              points={review.eval_graph}
              activePly={selectedPly}
              onSelectPly={setSelectedPly}
            />
          </Card>
        </section>

        <section className="review-side-col" aria-label="review summary">
          <Card>
            <h2 className="card-title">
              {hero}&apos;s report card
              {typeof heroAccuracy === 'number' && (
                <span className="review-accuracy">{heroAccuracy}% accuracy</span>
              )}
            </h2>
            <ul className="quality-legend">
              {QUALITY_ORDER.map((q) => (
                <li key={q} className={`quality-row quality-${q}`}>
                  <QualityBadge quality={q} />
                  <span>{qualityMeta(q).label}</span>
                  <strong>{review.counts?.[q] ?? 0}</strong>
                </li>
              ))}
            </ul>
            <p className="u-muted">
              Depth {review.depth} · {review.summary.ply_count} plies analysed by {review.provider}
            </p>
          </Card>

          <Card>
            <h2 className="card-title">
              <button
                type="button"
                className={`coach-star${coachOpen ? ' open' : ''}`}
                onClick={() => setCoachOpen((v) => !v)}
                aria-label="Coach assistant"
                aria-pressed={coachOpen}
                title="Ask the coach about this game"
              >
                <Star size={15} aria-hidden="true" />
              </button>
              <span className="coach-title-label">
                <Sparkles size={15} aria-hidden="true" /> Where to improve
              </span>
            </h2>
            {improvementsForHero.length === 0 ? (
              <p className="u-muted">
                No mistakes or blunders — your moves matched the engine&rsquo;s plan.
              </p>
            ) : (
              <ol className="improvement-list">
                {improvementsForHero.map((imp) => (
                  <li key={imp.ply}>
                    <button
                      type="button"
                      className="improvement"
                      onClick={() => setSelectedPly(imp.ply)}
                    >
                      <span>
                        Move {imp.ply}: played <strong>{imp.san}</strong>
                      </span>
                      <span className="u-muted">
                        {imp.loss_cp} cp lost · better was {imp.best_uci}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          {coachOpen && (
            <Card className="coach-card">
              <CoachAssistant
                gameId={gameId}
                focusPly={selected ? selected.ply : null}
                onSelectPly={(ply) => {
                  exitLesson();
                  setSelectedPly(ply);
                }}
                onPlayLine={playLine}
                onClose={() => setCoachOpen(false)}
              />
            </Card>
          )}

          <Card>
            <h2 className="card-title">Move-by-move classification</h2>
            <ol className="review-move-list" aria-label="classified moves">
              {review.moves.map((move) => (
                <li key={move.ply}>
                  <button
                    type="button"
                    className={`review-move${move.ply === selectedPly ? ' active' : ''}`}
                    onClick={() => setSelectedPly(move.ply)}
                  >
                    <span className="review-move-number">{move.move_number}</span>
                    <QualityBadge quality={move.quality} />
                    <span className={`review-san side-${move.color}`}>{move.san}</span>
                    <span className="review-excerpt">{move.explanation}</span>
                  </button>
                </li>
              ))}
            </ol>
          </Card>
        </section>
      </div>
    </main>
  );
}
