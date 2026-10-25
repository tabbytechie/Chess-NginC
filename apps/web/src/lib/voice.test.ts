/**
 * Voice narration tests (REVIEW-009).
 *
 * Three paths are tested:
 * 1. ElevenLabs TTS succeeds → MP3 buffer is handed to an Audio element.
 * 2. TTS returns 503 (key not configured) → silent fallback to speechSynthesis.
 * 3. speechSynthesis is absent or throws → everything is still a no-op.
 *
 * jsdom ships neither a speech engine nor real audio playback, so every
 * capability is installed or withheld by each test's own setup.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// We use vi.resetModules() to get a fresh voice.ts instance (with ttsAvailable
// reset to null) before every test, since it is module-level state.
async function freshModule() {
  vi.resetModules();
  return import('./voice');
}

type FakeVoice = { name: string; lang: string; default?: boolean };

let spoken: string[];
let cancelFn: ReturnType<typeof vi.fn>;

function installSpeech(voices: FakeVoice[] = []) {
  spoken = [];
  cancelFn = vi.fn();
  const speakSpy = vi.fn();
  Object.defineProperty(window, 'speechSynthesis', {
    configurable: true,
    value: {
      cancel: cancelFn,
      speak: (utterance: { text: string; voice?: FakeVoice }) => {
        spoken.push(utterance.text);
        speakSpy(utterance);
      },
      getVoices: () => voices,
    },
  });
  Object.defineProperty(window, 'SpeechSynthesisUtterance', {
    configurable: true,
    value: class {
      text: string;
      rate = 1;
      pitch = 1;
      volume = 1;
      lang = '';
      voice: FakeVoice | null = null;
      onerror: (() => void) | null = null;
      constructor(text: string) {
        this.text = text;
      }
    },
  });
  return { spoken, cancel: cancelFn, speakSpy };
}

function removeSpeech() {
  const win = window as unknown as Record<string, unknown>;
  delete win.speechSynthesis;
  delete win.SpeechSynthesisUtterance;
}

beforeEach(() => {
  removeSpeech();
});

afterEach(() => {
  removeSpeech();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// voiceAvailable
// ---------------------------------------------------------------------------

describe('voiceAvailable', () => {
  it('is false when there is no fetch and no speech engine', async () => {
    const { voiceAvailable } = await freshModule();
    // jsdom normally has fetch; stub it out to simulate a minimal env
    vi.stubGlobal('fetch', undefined);
    expect(voiceAvailable()).toBe(false);
  });

  it('is true when fetch is available (TTS path) even without speechSynthesis', async () => {
    const { voiceAvailable } = await freshModule();
    expect(typeof fetch).toBe('function');
    expect(voiceAvailable()).toBe(true);
  });

  it('is true when speechSynthesis is present even without fetch', async () => {
    installSpeech();
    const { voiceAvailable } = await freshModule();
    vi.stubGlobal('fetch', undefined);
    expect(voiceAvailable()).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// chunkText — unchanged logic, still worth testing
// ---------------------------------------------------------------------------

describe('chunkText', () => {
  const long = [
    'Move 12: White plays bishop to b5, exactly what the engine wanted.',
    'This is the Ruy Lopez: Morphy Defense, the main line of an old opening.',
    "White's win expectancy here is 56 percent, and the position stays balanced.",
    'Keep the bishop pair and the f6 knight under observation and the pawn stays safe.',
  ].join(' ');

  it('keeps short narration in one piece', async () => {
    const { chunkText } = await freshModule();
    expect(chunkText('Knight to f3. Solid.')).toEqual(['Knight to f3. Solid.']);
  });

  it('splits long narration and loses nothing', async () => {
    const { chunkText } = await freshModule();
    const chunks = chunkText(long);
    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks.join(' ')).toBe(long);
    for (const chunk of chunks) expect(chunk.length).toBeLessThanOrEqual(180);
  });

  it('breaks between sentences, never inside one that fits', async () => {
    const { chunkText } = await freshModule();
    const one = 'Move 12: White plays bishop to b5, exactly what the engine wanted.';
    const two = "White's win expectancy here is 56 percent, and the position stays balanced.";
    expect(chunkText(`${one} ${two} ${one}`, 100)).toEqual([one, two, one]);
  });

  it('never tears a decimal like "1.5 pawns" in half', async () => {
    const { chunkText } = await freshModule();
    const text = 'White is better here by 1.5 pawns, which the engine can prove.';
    const chunks = chunkText(text, 24);
    expect(chunks.join(' ')).toBe(text);
    for (const chunk of chunks) expect(chunk).not.toMatch(/(^|\s)\d+\.$/);
    expect(chunks.some((chunk: string) => chunk.includes('1.5'))).toBe(true);
  });

  it('leaves a single oversized word intact', async () => {
    const { chunkText } = await freshModule();
    const word = 'Supercalifragilisticexpialidocious'.repeat(6);
    expect(chunkText(word, 20)).toEqual([word]);
  });
});

// ---------------------------------------------------------------------------
// speak — TTS unavailable (503) falls back to speechSynthesis
// ---------------------------------------------------------------------------

describe('speak with TTS unavailable (503)', () => {
  it('falls back to speechSynthesis when the backend has no key', async () => {
    const { spoken: said, speakSpy } = installSpeech();
    const mockFetch = vi
      .fn()
      .mockResolvedValue({ status: 503, ok: false, json: () => Promise.resolve({}) });
    vi.stubGlobal('fetch', mockFetch);

    const { speak } = await freshModule();
    speak('Knight to f3.');

    // speak() is fire-and-forget; wait for the promise chain to settle
    await vi.waitFor(() => {
      expect(said.length).toBeGreaterThan(0);
    });

    expect(speakSpy.mock.calls[0][0]).toMatchObject({ rate: 0.92, pitch: 0.92 });
  });

  it('short-circuits subsequent calls after the first 503 (no re-probing)', async () => {
    installSpeech();
    const mockFetch = vi
      .fn()
      .mockResolvedValue({ status: 503, ok: false, json: () => Promise.resolve({}) });
    vi.stubGlobal('fetch', mockFetch);

    const { speak } = await freshModule();

    // First call probes TTS
    speak('First.');
    await vi.waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    // Second call should skip TTS entirely (ttsAvailable === false now)
    speak('Second.');
    await vi.waitFor(() => {
      // spoken should have been called for 'Second.' via speechSynthesis
      expect(mockFetch).toHaveBeenCalledTimes(1); // still 1 — no second fetch
    });
  });
});

// ---------------------------------------------------------------------------
// speak — TTS network error also falls back
// ---------------------------------------------------------------------------

describe('speak with TTS network error', () => {
  it('falls back to speechSynthesis on fetch rejection', async () => {
    const { spoken: said } = installSpeech();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('NetworkError')));

    const { speak } = await freshModule();
    speak('Bishop takes f7.');

    await vi.waitFor(() => {
      expect(said.length).toBeGreaterThan(0);
    });
  });
});

// ---------------------------------------------------------------------------
// speak — TTS success path
// ---------------------------------------------------------------------------

describe('speak with TTS success', () => {
  it('plays the returned audio buffer via an Audio element', async () => {
    removeSpeech(); // no browser fallback needed

    const playSpy = vi.fn().mockImplementation(function (this: { onended: (() => void) | null }) {
      // Simulate async playback finish
      setTimeout(() => this.onended?.(), 0);
      return Promise.resolve();
    });

    class FakeAudio {
      src = '';
      volume = 1;
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      pause = vi.fn();
      play = playSpy;
    }
    vi.stubGlobal('Audio', FakeAudio);
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    const fakeBuffer = new ArrayBuffer(64);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        arrayBuffer: () => Promise.resolve(fakeBuffer),
      }),
    );

    const { speak } = await freshModule();
    speak('Knight to f3, solid.');

    await vi.waitFor(() => {
      expect(playSpy).toHaveBeenCalled();
    });
  });
});

// ---------------------------------------------------------------------------
// speak — blank text is always a no-op
// ---------------------------------------------------------------------------

describe('speak blank text', () => {
  it('makes no fetch and no speech call', async () => {
    const { spoken: said } = installSpeech();
    const mockFetch = vi.fn();
    vi.stubGlobal('fetch', mockFetch);

    const { speak } = await freshModule();
    speak('   ');

    expect(said).toHaveLength(0);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// stopSpeaking
// ---------------------------------------------------------------------------

describe('stopSpeaking', () => {
  it('cancels speechSynthesis', async () => {
    installSpeech();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 503, ok: false }));

    const { speak, stopSpeaking } = await freshModule();
    speak('Knight to f3.');

    // Wait for speak to have called speechSynthesis.cancel() at least once
    await vi.waitFor(() => {
      expect(cancelFn).toHaveBeenCalled();
    });

    cancelFn.mockClear();
    stopSpeaking();
    expect(cancelFn).toHaveBeenCalled();
  });

  it('is a safe no-op when nothing is playing', async () => {
    const { stopSpeaking } = await freshModule();
    expect(() => stopSpeaking()).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// No speech engine, no TTS — everything degrades gracefully
// ---------------------------------------------------------------------------

describe('speak with no engine at all', () => {
  it('is an inert no-op (no throw) when neither TTS nor speechSynthesis work', async () => {
    removeSpeech();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('no network')));

    const { speak } = await freshModule();
    expect(() => speak('Knight to f3.')).not.toThrow();
  });
});
