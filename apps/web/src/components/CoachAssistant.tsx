/**
 * Coach assistant panel (Phase 11): a conversational read of the reviewed game,
 * opened from the ⭐ next to "Where to improve".
 *
 * Everything it shows is grounded — the answer text, the moves it cites and the
 * board position it returns all come from engine + book facts about *this* game
 * (or the player's own indexed games for cross-game patterns). Clicking a cited
 * move walks the review tour to that ply, so the coach and the board stay in sync.
 *
 * The panel is dumb: it owns only its question box and the running thread, and
 * talks to the API through the shared client. A 429/error is surfaced inline so
 * the surrounding review never disappears because the coach had nothing to say.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Lightbulb, Loader2, PlayCircle, Send, Volume2, X } from 'lucide-react';

import { Button } from './ui/Button';
import VoicePicker, { type VoicePickerOption } from './VoicePicker';
import { ApiError, api } from '../lib/api-client';
import type {
  AssistantAnswerResponse,
  AssistantLineStep,
  CoachPattern,
  VoiceOption,
} from '../lib/api-types';
import {
  listBrowserVoices,
  setVoiceSelection,
  speak,
  stopSpeaking,
  voiceAvailable,
  type BrowserVoice,
  type VoiceSelection,
} from '../lib/voice';

type Props = {
  gameId: number;
  /** Ply the review cursor sits on; the coach resolves focus from it. */
  focusPly: number | null;
  /** Walk the review tour to a ply when a cited move is clicked. */
  onSelectPly: (ply: number) => void;
  /** Drive the main board through a walkable variation the coach surfaced. */
  onPlayLine: (line: AssistantLineStep[], title: string) => void;
  onClose: () => void;
};

type Turn = {
  id: number;
  role: 'you' | 'coach';
  text: string;
  answer?: AssistantAnswerResponse;
};

/** How many recent turns ride along so follow-ups resolve against context. */
const HISTORY_MAX = 8;

/** Quick prompts that turn a vague question into a coachable one. */
const SUGGESTIONS = [
  'What was my worst move and why?',
  'Show me the main line here',
  'Why is that better?',
  'What is the idea behind this move?',
];

/** Short, human labels for the coach's detected intent. */
const INTENT_LABEL: Record<string, string> = {
  summary: 'Overview',
  plan: 'Best way to proceed',
  lesson: "Let's walk it",
  why: 'Why it is better',
  idea: 'The idea',
  alternatives: 'Other ways it could have gone',
  position: 'The position',
  explain: 'Why that move',
  patterns: 'Across your games',
  opening: 'Opening theory',
  general: 'Coach',
};

/** Map a stored voice id to a narrator selection given the premium-voice ids.
 *  Empty = browser default (null, i.e. try ElevenLabs then fall back); a known
 *  ElevenLabs id = premium engine; anything else = a browser OS voice name. */
function selectionFor(id: string, elevenIds: Set<string>): VoiceSelection | null {
  if (!id) return null;
  return elevenIds.has(id) ? { engine: 'eleven', id } : { engine: 'browser', id };
}

export default function CoachAssistant({
  gameId,
  focusPly,
  onSelectPly,
  onPlayLine,
  onClose,
}: Props) {
  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [patterns, setPatterns] = useState<CoachPattern[] | null>(null);
  const [patternSummary, setPatternSummary] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceOn, setVoiceOn] = useState(false);
  const [voiceId, setVoiceId] = useState('');
  const [elevenVoices, setElevenVoices] = useState<VoiceOption[]>([]);
  const [browserVoices, setBrowserVoices] = useState<BrowserVoice[]>(() => listBrowserVoices());
  const [voiceReady] = useState(() => voiceAvailable());
  const [savingVoice, setSavingVoice] = useState(false);
  const nextId = useRef(1);
  const threadRef = useRef<HTMLDivElement | null>(null);

  const elevenIds = useCallback(() => new Set(elevenVoices.map((v) => v.id)), [elevenVoices]);

  // Load consent + chosen voice (server-side) and the free voice catalog once.
  // Degrades quietly: an unconfigured/offline backend leaves the defaults and a
  // silent coach rather than throwing over the review.
  useEffect(() => {
    let alive = true;
    const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined;
    const onVoicesChanged = () => {
      if (alive) setBrowserVoices(listBrowserVoices());
    };
    synth?.addEventListener?.('voiceschanged', onVoicesChanged);
    (async () => {
      try {
        const [prefs, catalog] = await Promise.all([api.getVoicePrefs(), api.listVoices()]);
        if (!alive) return;
        setVoiceOn(prefs.voice_authorized);
        setVoiceId(prefs.voice_id);
        setElevenVoices(catalog.voices);
        setVoiceSelection(selectionFor(prefs.voice_id, new Set(catalog.voices.map((v) => v.id))));
      } catch {
        /* no backend voice config yet: defaults stand */
      }
    })();
    return () => {
      alive = false;
      synth?.removeEventListener?.('voiceschanged', onVoicesChanged);
    };
  }, []);

  // Closing the panel must not leave the coach talking over the page.
  useEffect(() => () => stopSpeaking(), []);

  const push = useCallback((turn: Omit<Turn, 'id'>) => {
    setTurns((prev) => [...prev, { ...turn, id: nextId.current++ }]);
  }, []);

  // Keep the newest turn in view as the conversation grows.
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns, patterns, error]);

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    // Send the prior thread (not the question being asked now) as history.
    const history = turns
      .map((t) => ({ role: t.role === 'you' ? 'user' : 'coach', text: t.text }))
      .slice(-HISTORY_MAX);
    setQuestion('');
    setError(null);
    setBusy(true);
    push({ role: 'you', text });
    try {
      const answer = await api.askCoach(gameId, {
        question: text,
        focus_ply: focusPly ?? null,
        history,
      });
      push({ role: 'coach', text: answer.answer, answer });
      // Speak the answer only when the user has authorized the coach's voice.
      if (voiceOn) speak(answer.answer);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The coach could not answer just now.');
    } finally {
      setBusy(false);
    }
  }

  async function loadPatterns() {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const res = await api.coachPatterns(gameId);
      setPatterns(res.items);
      setPatternSummary(res.summary);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No cross-game patterns to show yet.');
    } finally {
      setBusy(false);
    }
  }

  // Persist a voice change and reflect the server's answer; on failure keep the
  // local choice so the UI never fights an offline backend.
  async function saveVoice(patch: { voice_authorized?: boolean; voice_id?: string }) {
    setSavingVoice(true);
    try {
      const res = await api.saveVoicePrefs(patch);
      setVoiceOn(res.voice_authorized);
      setVoiceId(res.voice_id);
    } catch {
      /* optimistic: the selection still applies to this session via voice.ts */
    } finally {
      setSavingVoice(false);
    }
  }

  function toggleConsent() {
    const next = !voiceOn;
    if (!next) stopSpeaking();
    setVoiceOn(next);
    void saveVoice({ voice_authorized: next });
  }

  function pickVoice(id: string) {
    setVoiceId(id);
    setVoiceSelection(selectionFor(id, elevenIds()));
    void saveVoice({ voice_id: id });
  }

  // ElevenLabs free voices first (the primary engine), then the OS voices; the
  // picker groups them under headings and greys out any that need a key.
  const voiceOptions: VoicePickerOption[] = [
    ...elevenVoices.map((v) => ({
      id: v.id,
      name: v.name,
      kind: 'eleven' as const,
      available: v.available,
    })),
    ...browserVoices.map((v) => ({
      id: v.id,
      name: v.name,
      kind: 'browser' as const,
      available: true,
    })),
  ];

  return (
    <section className="coach-panel" aria-label="coach assistant">
      <header className="coach-head">
        <h2 className="card-title">Coach assistant</h2>
        <Button variant="ghost" className="coach-close" onClick={onClose} aria-label="Close coach">
          <X size={15} aria-hidden="true" />
        </Button>
      </header>

      {voiceReady && (
        <div className="coach-voice" role="group" aria-label="coach voice settings">
          <label className="coach-voice-consent">
            <input
              type="checkbox"
              checked={voiceOn}
              onChange={toggleConsent}
              disabled={savingVoice}
            />
            <Volume2 size={14} aria-hidden="true" />
            Let the coach speak
          </label>
          <VoicePicker
            label="Narration voice"
            value={voiceId}
            options={voiceOptions}
            groups
            defaultOption={{ value: '', label: 'System default' }}
            placeholder="System default"
            onChange={pickVoice}
            disabled={savingVoice}
          />
        </div>
      )}

      <div className="coach-thread" ref={threadRef}>
        {turns.length === 0 && !patterns && (
          <p className="u-muted">
            Ask about this game — the positions, the best way to proceed, or how it could have gone
            differently. Answers are drawn only from the engine analysis of your own moves.
          </p>
        )}
        {turns.map((turn) =>
          turn.role === 'you' ? (
            <p key={turn.id} className="coach-turn coach-you">
              {turn.text}
            </p>
          ) : (
            <div key={turn.id} className="coach-turn coach-answer">
              <p className="coach-intent">
                {INTENT_LABEL[turn.answer?.intent ?? ''] ?? 'Coach'}
                {turn.answer?.mode === 'llm' ? ' · phrased by a model, cited from your game' : ''}
              </p>
              <div className="coach-text">
                {turn.text
                  .split('\n')
                  .filter((line) => line.trim() !== '')
                  .map((line, i) => (
                    <p key={`${turn.id}-l${i}`}>{line}</p>
                  ))}
              </div>
              {turn.answer && turn.answer.line && turn.answer.line.length > 0 && (
                <button
                  type="button"
                  className="coach-line-link"
                  onClick={() =>
                    onPlayLine(turn.answer?.line ?? [], turn.answer?.line_title ?? 'The line')
                  }
                >
                  <PlayCircle size={14} aria-hidden="true" />
                  Show this line on the board
                </button>
              )}
              {turn.answer?.position_fen && (
                <button
                  type="button"
                  className="coach-board-link"
                  onClick={() => onSelectPly(turn.answer?.references?.[0]?.ply ?? focusPly ?? 0)}
                >
                  Show the position on the board
                </button>
              )}
              {turn.answer && turn.answer.references.length > 0 && (
                <ul className="coach-refs" aria-label="moves this answer cites">
                  {turn.answer.references.map((ref) => (
                    <li key={`${turn.id}-${ref.ply}`}>
                      <button
                        type="button"
                        className="coach-ref"
                        onClick={() => onSelectPly(ref.ply)}
                        title={ref.note || undefined}
                      >
                        <span className={`review-san side-${ref.color}`}>{ref.san}</span>
                        <span className="u-muted">move {ref.ply}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ),
        )}
      </div>

      {patterns && (
        <div className="coach-patterns" aria-label="cross-game patterns">
          <h3 className="coach-patterns-title">Where you slip most</h3>
          {patternSummary && <p className="u-muted">{patternSummary}</p>}
          {patterns.length === 0 ? (
            <p className="u-muted">No repeated errors found across your reviewed games yet.</p>
          ) : (
            <ul aria-label="error counts by opening">
              {patterns.map((p) => (
                <li key={p.opening_family} className="coach-pattern">
                  <strong>{p.opening_family}</strong>
                  <span className="u-muted">
                    {p.blunders} blunder{p.blunders === 1 ? '' : 's'} · {p.mistakes} mistake
                    {p.mistakes === 1 ? '' : 's'} · avg {p.avg_loss_cp} cp
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {error && <p role="alert">{error}</p>}

      {turns.length === 0 && (
        <div className="coach-chips" aria-label="suggested questions">
          {SUGGESTIONS.map((tip) => (
            <button
              key={tip}
              type="button"
              className="coach-chip"
              onClick={() => setQuestion(tip)}
              disabled={busy}
            >
              {tip}
            </button>
          ))}
        </div>
      )}

      <form className="coach-ask" onSubmit={ask}>
        <label className="sr-only" htmlFor="coach-question">
          Ask the coach about this game
        </label>
        <input
          id="coach-question"
          className="coach-input"
          type="text"
          maxLength={400}
          value={question}
          placeholder="e.g. What was my worst move and why?"
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
        />
        <Button type="submit" aria-label="Send question" disabled={busy || question.trim() === ''}>
          {busy ? (
            <Loader2 size={15} className="spin" aria-hidden="true" />
          ) : (
            <Send size={15} aria-hidden="true" />
          )}
          Ask
        </Button>
        <Button
          variant="ghost"
          type="button"
          aria-label="Show patterns"
          onClick={loadPatterns}
          disabled={busy}
        >
          <Lightbulb size={15} aria-hidden="true" />
          Patterns
        </Button>
      </form>
    </section>
  );
}
