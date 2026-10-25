/**
 * Spoken narration for the review tour (REVIEW-009).
 *
 * Two engines, one interface:
 * 1. ElevenLabs TTS via the FastAPI proxy — richer voices, costs free-tier
 *    characters (10 000/month, no credit card). The API key never reaches
 *    the browser; only the backend's `/api/v1/tts` endpoint sees it.
 * 2. Browser speechSynthesis — always available, zero quota, lower quality.
 *
 * `speak()` tries ElevenLabs first and silently falls back to the browser
 * engine on any failure (503 = key not configured, 429 = quota exhausted,
 * network error). Once a 503 is seen the TTS probe is short-circuited for
 * the rest of the page session so there is no repeated latency penalty.
 *
 * Fully guarded — in jsdom, or any environment without audio or speech
 * support, every function here is an inert no-op rather than a throw.
 */

import { API_BASE } from './api-client';

const TTS_URL = `${API_BASE}/api/v1/tts`;

/**
 * The voice the narrator should use. `eleven` forwards the id to the server
 * proxy (allowlisted there); `browser` matches a `speechSynthesis` voice by name.
 * `null` keeps the original behaviour: try ElevenLabs default, fall back to the
 * best browser voice.
 */
export type VoiceSelection = { engine: 'eleven' | 'browser'; id: string };

// Names/URIs of the OS voices this browser can speak with, for the picker.
export type BrowserVoice = { id: string; name: string };

// A calm, authoritative read: slightly slower than the default and a touch
// below the default pitch. Composed narration sounds rushed at rate 1.
const VOICE_RATE = 0.92;
const VOICE_PITCH = 0.92;
const VOICE_VOLUME = 1;

// Chrome silently abandons an utterance after roughly 15 seconds of speech; a
// rate-0.92 voice gets through something like 180 characters in that window, so
// fallback narration is chunked well inside it.
const MAX_CHUNK = 180;

// Preference order, not a claim that these exist everywhere: English
// narration/documentary voices tend to be the composed ones, and the platform's
// own voice list is the only authority on which are installed.
const VOICE_HINTS = [
  'Daniel',
  'Google UK English Male',
  'Arthur',
  'Oliver',
  'Microsoft George',
  'David',
  'Google US English',
];

// ---------------------------------------------------------------------------
// Internal state (module-level singletons — only one narrator at a time)
// ---------------------------------------------------------------------------

// Set to false after a 503 response so subsequent calls skip the fetch and
// go straight to the speechSynthesis fallback for the rest of the session.
let ttsAvailable: boolean | null = null;

// The narrator's chosen voice (null = defaults). Module-level singleton so the
// coach panel and the review tour share one narrator configuration.
let selection: VoiceSelection | null = null;

// The currently playing HTMLAudioElement (null when idle).
let activeAudio: HTMLAudioElement | null = null;

// AbortController for the in-flight TTS fetch (null when idle).
let activeAbort: AbortController | null = null;

// ---------------------------------------------------------------------------
// speechSynthesis helpers (fallback path — identical logic to original)
// ---------------------------------------------------------------------------

function engine(): SpeechSynthesis | null {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return null;
  if (typeof window.SpeechSynthesisUtterance !== 'function') return null;
  return window.speechSynthesis;
}

/** Whether this browser can narrate at all; the UI hides the toggle if not. */
export function voiceAvailable(): boolean {
  // TTS endpoint is always potentially available; browser engine may not be.
  return typeof fetch !== 'undefined' || engine() !== null;
}

/**
 * The OS voices this browser offers, for the picker. Names are the stable
 * handle we persist (voice URIs vary across platforms); de-duplicated because
 * some browsers list the same voice once per locale.
 */
export function listBrowserVoices(): BrowserVoice[] {
  const synth = engine();
  if (!synth) return [];
  const seen = new Set<string>();
  const out: BrowserVoice[] = [];
  for (const voice of synth.getVoices()) {
    if (seen.has(voice.name)) continue;
    seen.add(voice.name);
    out.push({ id: voice.name, name: voice.name });
  }
  return out;
}

/** Choose the narrator's voice for the whole session (null restores defaults). */
export function setVoiceSelection(next: VoiceSelection | null): void {
  selection = next;
  // A fresh selection re-arms the ElevenLabs probe: a previous 503 should not
  // keep short-circuiting a voice the user has only now chosen.
  if (next?.engine === 'eleven') ttsAvailable = null;
}

export function getVoiceSelection(): VoiceSelection | null {
  return selection;
}

function pickVoice(
  voices: SpeechSynthesisVoice[],
  preferred?: string,
): SpeechSynthesisVoice | null {
  if (voices.length === 0) return null;
  if (preferred) {
    const exact = voices.find((voice) => voice.name === preferred);
    if (exact) return exact;
  }
  for (const hint of VOICE_HINTS) {
    const match = voices.find((voice) => voice.name.toLowerCase().includes(hint.toLowerCase()));
    if (match) return match;
  }
  return (
    voices.find((voice) => voice.lang?.startsWith('en-GB')) ??
    voices.find((voice) => voice.lang?.startsWith('en')) ??
    voices.find((voice) => voice.default) ??
    null
  );
}

/**
 * Split narration into speakable chunks, breaking between sentences whenever
 * one fits. Splitting on punctuation alone would tear "1.5 pawns" in two, so
 * this walks words and only closes a chunk on sentence-final punctuation.
 *
 * Exported for unit tests.
 */
export function chunkText(text: string, max = MAX_CHUNK): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const chunks: string[] = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (current && candidate.length > max) {
      chunks.push(current);
      current = word;
      continue;
    }
    current = candidate;
    if (current.length >= max * 0.6 && /[.!?]$/.test(current)) {
      chunks.push(current);
      current = '';
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

function speakWithBrowser(text: string): void {
  const synth = engine();
  if (!synth) return;
  try {
    synth.cancel();
    const preferred = selection?.engine === 'browser' ? selection.id : undefined;
    const voice = pickVoice(synth.getVoices(), preferred);
    for (const chunk of chunkText(text)) {
      const utterance = new SpeechSynthesisUtterance(chunk);
      utterance.rate = VOICE_RATE;
      utterance.pitch = VOICE_PITCH;
      utterance.volume = VOICE_VOLUME;
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
      }
      // Aborted/blocked speech is normal during fast navigation: stay silent.
      utterance.onerror = () => {};
      synth.speak(utterance);
    }
  } catch {
    /* narration is an enhancement; it must never break the review page */
  }
}

// ---------------------------------------------------------------------------
// ElevenLabs TTS helpers
// ---------------------------------------------------------------------------

/** Stop any in-flight audio and abort any pending fetch. */
function cancelActivePlayback(): void {
  if (activeAbort) {
    activeAbort.abort();
    activeAbort = null;
  }
  if (activeAudio) {
    activeAudio.pause();
    activeAudio.src = '';
    activeAudio = null;
  }
  try {
    engine()?.cancel();
  } catch {
    /* speechSynthesis may be unavailable; ignore */
  }
}

async function fetchTTSAudio(
  text: string,
  signal: AbortSignal,
): Promise<ArrayBuffer | 'unavailable' | 'error'> {
  if (ttsAvailable === false) return 'unavailable';
  const elevenVoice = selection?.engine === 'eleven' ? selection.id : '';
  try {
    const resp = await fetch(TTS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ text, voice: elevenVoice }),
      signal,
    });
    if (resp.status === 503) {
      // Key not configured — stop probing for the rest of this session.
      ttsAvailable = false;
      return 'unavailable';
    }
    if (!resp.ok) return 'error';
    ttsAvailable = true;
    return await resp.arrayBuffer();
  } catch (err: unknown) {
    if ((err as Error).name === 'AbortError') return 'error';
    return 'error';
  }
}

function playAudioBuffer(buffer: ArrayBuffer): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof Audio === 'undefined') {
      reject(new Error('no audio support'));
      return;
    }
    const blob = new Blob([buffer], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.volume = VOICE_VOLUME;
    activeAudio = audio;
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (activeAudio === audio) activeAudio = null;
      resolve();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      if (activeAudio === audio) activeAudio = null;
      reject(new Error('audio playback failed'));
    };
    audio.play().catch((err: unknown) => {
      URL.revokeObjectURL(url);
      if (activeAudio === audio) activeAudio = null;
      reject(err);
    });
  });
}

// ---------------------------------------------------------------------------
// Public interface
// ---------------------------------------------------------------------------

/**
 * Speak `text`, replacing anything already being said.
 *
 * Tries ElevenLabs TTS first (richer voice); falls back to the browser's
 * speechSynthesis engine transparently. Fire-and-forget — returns void; use
 * `stopSpeaking()` to cancel mid-utterance (e.g. on page unmount).
 */
export function speak(text: string): void {
  const trimmed = text.trim();
  if (!trimmed) return;

  // Cancel whatever is currently playing or being fetched.
  cancelActivePlayback();

  // A chosen browser voice never touches the proxy — speak with it directly.
  if (selection?.engine === 'browser') {
    speakWithBrowser(trimmed);
    return;
  }

  // Fast path: TTS is known-unavailable → use browser engine immediately.
  if (ttsAvailable === false) {
    speakWithBrowser(trimmed);
    return;
  }

  const controller = new AbortController();
  activeAbort = controller;

  fetchTTSAudio(trimmed, controller.signal)
    .then((result) => {
      // If this controller was aborted while we were fetching, discard.
      if (controller.signal.aborted) return;

      if (result === 'unavailable' || result === 'error') {
        speakWithBrowser(trimmed);
        return;
      }
      return playAudioBuffer(result).catch(() => {
        // Audio playback failed (e.g. MIME not supported) — use browser engine.
        if (!controller.signal.aborted) speakWithBrowser(trimmed);
      });
    })
    .catch(() => {
      /* fetch threw unexpectedly; browser fallback is the safe response */
      if (!controller.signal.aborted) speakWithBrowser(trimmed);
    });
}

/** Silence the narrator (called when the page unmounts or voice is switched off). */
export function stopSpeaking(): void {
  cancelActivePlayback();
}
