/**
 * Coach assistant panel tests (Phase 11): asking a question, the moves it cites
 * walking the review tour, cross-game pattern recall, and the offline-friendly
 * error surface. The API is always mocked — nothing here reaches a real engine.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ComponentProps } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CoachAssistant from './CoachAssistant';
import { ApiError, api } from '../lib/api-client';
import * as voice from '../lib/voice';
import type {
  AssistantAnswerResponse,
  AssistantLineStep,
  CoachPatternsResponse,
  VoiceOption,
} from '../lib/api-types';

// The coach panel hydrates its voice bar on mount; keep those calls mocked and
// offline-safe so no test reaches the network and defaults stay deterministic.
// Speak/selection are the narrator side effects we assert on, so swap just those
// while keeping the real availability/list helpers the component also calls.
vi.mock('../lib/voice', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/voice')>();
  return {
    ...actual,
    speak: vi.fn(),
    stopSpeaking: vi.fn(),
    setVoiceSelection: vi.fn(),
  };
});

beforeEach(() => {
  vi.spyOn(api, 'getVoicePrefs').mockResolvedValue({ voice_authorized: false, voice_id: '' });
  vi.spyOn(api, 'listVoices').mockResolvedValue({ voices: [] });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

const ANSWER: AssistantAnswerResponse = {
  answer: 'Your c5 blunder hung a pawn; the engine preferred e5.',
  intent: 'explain',
  mode: 'deterministic',
  provider: 'stockfish+book',
  references: [
    { ply: 2, san: 'c5', color: 'b', note: 'hangs a pawn' },
    { ply: 4, san: 'Nf6', color: 'b', note: '' },
  ],
  position_fen: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
};

const LINE_ANSWER: AssistantAnswerResponse = {
  answer:
    'Recommendation: play e5 instead of c5.\nThe idea: strike the centre.\nThe line: e5 Nf3 d6.',
  intent: 'plan',
  mode: 'deterministic',
  provider: 'stockfish+book',
  references: [{ ply: 2, san: 'c5', color: 'b', note: '' }],
  position_fen: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
  line_title: 'How the game went',
  line: [
    {
      san: 'e5',
      uci: 'e7e5',
      color: 'b',
      fen_before: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
      fen_after: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2',
      comment: 'best',
      source: 'played',
      ply: 2,
    },
  ] as AssistantLineStep[],
};

function renderPanel(overrides: Partial<ComponentProps<typeof CoachAssistant>> = {}) {
  const onSelectPly = vi.fn();
  const onPlayLine = vi.fn();
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(
    <CoachAssistant
      gameId={7}
      focusPly={2}
      onSelectPly={onSelectPly}
      onPlayLine={onPlayLine}
      onClose={onClose}
      {...overrides}
    />,
  );
  return { user, onSelectPly, onPlayLine, onClose };
}

describe('CoachAssistant asking', () => {
  it('sends the question with the current focus and renders the grounded answer', async () => {
    const ask = vi.spyOn(api, 'askCoach').mockResolvedValue(ANSWER);
    const { user, onSelectPly } = renderPanel();

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'what went wrong?');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    expect(await screen.findByText(ANSWER.answer)).toBeInTheDocument();
    expect(ask).toHaveBeenCalledWith(7, {
      question: 'what went wrong?',
      focus_ply: 2,
      history: [],
    });

    // Your question is echoed in the thread.
    expect(screen.getByText('what went wrong?')).toBeInTheDocument();

    // Clicking a cited move walks the review tour to that ply.
    const refs = screen.getByRole('list', { name: 'moves this answer cites' });
    await user.click(within(refs).getByText('c5'));
    expect(onSelectPly).toHaveBeenCalledWith(2);
  });

  it('disables Ask until a question is typed', () => {
    renderPanel();
    expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
  });

  it('surfaces an API error without leaving the panel blank', async () => {
    vi.spyOn(api, 'askCoach').mockRejectedValue(new ApiError(429, 'Slow down a moment.'));
    const { user } = renderPanel();

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'hi');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Slow down a moment.');
  });
});

describe('CoachAssistant cross-game patterns', () => {
  it('loads and lists the openings where the player errs most', async () => {
    const res: CoachPatternsResponse = {
      summary: 'Most of your errors come in the Sicilian Defense.',
      items: [
        {
          opening_family: 'Sicilian Defense',
          mistakes: 1,
          blunders: 2,
          total_errors: 3,
          avg_loss_cp: 180,
        },
      ],
    };
    const patterns = vi.spyOn(api, 'coachPatterns').mockResolvedValue(res);
    const { user } = renderPanel();

    await user.click(screen.getByRole('button', { name: 'Show patterns' }));

    expect(patterns).toHaveBeenCalledWith(7);
    const panel = await screen.findByLabelText('cross-game patterns');
    expect(within(panel).getByText('Sicilian Defense')).toBeInTheDocument();
    expect(within(panel).getByText('2 blunders · 1 mistake · avg 180 cp')).toBeInTheDocument();
  });
});

describe('CoachAssistant closing', () => {
  it('calls onClose when the close button is pressed', async () => {
    const { user, onClose } = renderPanel();
    await user.click(screen.getByRole('button', { name: 'Close coach' }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe('CoachAssistant conversation memory and line walks', () => {
  it('sends the prior thread as history so follow-ups resolve', async () => {
    const ask = vi
      .spyOn(api, 'askCoach')
      .mockResolvedValueOnce(ANSWER)
      .mockResolvedValueOnce({ ...ANSWER, answer: 'After that, develop with a gain.' });
    const { user } = renderPanel();

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'what went wrong?');
    await user.click(screen.getByRole('button', { name: 'Send question' }));
    await screen.findByText(ANSWER.answer);

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'and after that?');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    expect(ask).toHaveBeenLastCalledWith(7, {
      question: 'and after that?',
      focus_ply: 2,
      history: [
        { role: 'user', text: 'what went wrong?' },
        { role: 'coach', text: ANSWER.answer },
      ],
    });
  });

  it('renders a multi-section answer one line at a time', async () => {
    vi.spyOn(api, 'askCoach').mockResolvedValue(LINE_ANSWER);
    const { user } = renderPanel();

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'best move?');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    expect(await screen.findByText('Recommendation: play e5 instead of c5.')).toBeInTheDocument();
    expect(screen.getByText('The idea: strike the centre.')).toBeInTheDocument();
  });

  it('shows a walkable line and drives the board when asked', async () => {
    vi.spyOn(api, 'askCoach').mockResolvedValue(LINE_ANSWER);
    const { user, onPlayLine } = renderPanel();

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'show me the line');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    const play = await screen.findByRole('button', { name: /Show this line on the board/i });
    await user.click(play);
    expect(onPlayLine).toHaveBeenCalledWith(LINE_ANSWER.line, 'How the game went');
  });
});

async function askOnce(user: ReturnType<typeof userEvent.setup>, text = 'what went wrong?') {
  await user.type(screen.getByLabelText('Ask the coach about this game'), text);
  await user.click(screen.getByRole('button', { name: 'Send question' }));
  return screen.findByText(ANSWER.answer);
}

describe('CoachAssistant voice', () => {
  it('stays silent when the coach voice is not authorized', async () => {
    // Default prefs mock: voice_authorized false.
    vi.spyOn(api, 'askCoach').mockResolvedValue(ANSWER);
    const { user } = renderPanel();
    await askOnce(user);
    expect(voice.speak).not.toHaveBeenCalled();
  });

  it('speaks the answer once the stored preference authorizes the voice', async () => {
    vi.spyOn(api, 'getVoicePrefs').mockResolvedValue({ voice_authorized: true, voice_id: '' });
    vi.spyOn(api, 'askCoach').mockResolvedValue(ANSWER);
    const { user } = renderPanel();

    const consent = await screen.findByRole('checkbox', { name: 'Let the coach speak' });
    await waitFor(() => expect(consent).toBeChecked());

    await askOnce(user);
    expect(voice.speak).toHaveBeenCalledWith(ANSWER.answer);
  });

  it('persists the consent toggle when the user authorizes the coach', async () => {
    const save = vi
      .spyOn(api, 'saveVoicePrefs')
      .mockResolvedValue({ voice_authorized: true, voice_id: '' });
    const { user } = renderPanel();

    const consent = await screen.findByRole('checkbox', { name: 'Let the coach speak' });
    expect(consent).not.toBeChecked();
    await user.click(consent);

    expect(save).toHaveBeenCalledWith({ voice_authorized: true });
    await waitFor(() => expect(consent).toBeChecked());
  });

  it('lists the free premium catalog and forwards a pick to selection and storage', async () => {
    const catalog: VoiceOption[] = [
      { id: 'OnwK4e9ZLuTAKqWW03F9', name: 'Daniel', engine: 'eleven', available: true },
      { id: '21m00Tcm4TlvDq8ikWAM', name: 'Rachel', engine: 'eleven', available: true },
    ];
    vi.spyOn(api, 'listVoices').mockResolvedValue({ voices: catalog });
    const save = vi
      .spyOn(api, 'saveVoicePrefs')
      .mockResolvedValue({ voice_authorized: false, voice_id: 'OnwK4e9ZLuTAKqWW03F9' });
    const { user } = renderPanel();

    const select = await screen.findByLabelText('Narration voice');
    await waitFor(() =>
      expect(within(select).getByRole('option', { name: 'Rachel' })).toBeInTheDocument(),
    );

    await user.selectOptions(select, 'OnwK4e9ZLuTAKqWW03F9');
    expect(voice.setVoiceSelection).toHaveBeenCalledWith({
      engine: 'eleven',
      id: 'OnwK4e9ZLuTAKqWW03F9',
    });
    expect(save).toHaveBeenCalledWith({ voice_id: 'OnwK4e9ZLuTAKqWW03F9' });
  });

  it('marks a premium voice unavailable when no key is configured', async () => {
    const catalog: VoiceOption[] = [
      { id: 'pNInz6obpgDQGcFmaJgB', name: 'Adam', engine: 'eleven', available: false },
    ];
    vi.spyOn(api, 'listVoices').mockResolvedValue({ voices: catalog });
    renderPanel();

    const select = await screen.findByLabelText('Narration voice');
    const option = await waitFor(() => within(select).getByRole('option', { name: /Adam/ }));
    expect(option).toBeDisabled();
  });
});
