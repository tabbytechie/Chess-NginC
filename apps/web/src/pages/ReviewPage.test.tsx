/**
 * Review-page tests: cached-vs-generated review loading, classification
 * rendering, the board replay (tour navigation, keyboard, opening and odds) and
 * the improvement shortcuts (REVIEW-001..009).
 */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../app/AuthContext';
import { ApiError, api } from '../lib/api-client';
import type { ReviewResponse, VoiceOption, VoicePreferences } from '../lib/api-types';
import * as settings from '../lib/settings';
import ReviewPage from './ReviewPage';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1';

function review(overrides: Partial<ReviewResponse> = {}): ReviewResponse {
  return {
    id: 3,
    game_id: 7,
    status: 'completed',
    provider: 'stockfish',
    depth: 15,
    hero_color: 'w',
    error: null,
    summary: { ply_count: 2, accuracy: { w: 92, b: 71 } },
    counts: { best: 1, excellent: 0, good: 1, inaccuracy: 0, mistake: 0, blunder: 0, brilliant: 0 },
    moves: [
      {
        ply: 1,
        move_number: 1,
        uci: 'e2e4',
        san: 'e4',
        pre_fen: START_FEN,
        color: 'w',
        quality: 'best',
        centipawn_loss: 0,
        best_uci: 'e2e4',
        eval_cp: 20,
        eval_mate: null,
        explanation: 'e4 is exactly what the engine wants. Well played.',
        // What the API derives on read from the theory book (REVIEW-008).
        opening_eco: 'B00',
        opening_name: "King's Pawn Game",
        in_book: true,
        win_pct: 76,
      },
      {
        ply: 2,
        move_number: 1,
        uci: 'e7e5',
        san: 'e5',
        pre_fen: AFTER_E4,
        color: 'b',
        quality: 'good',
        centipawn_loss: 25,
        best_uci: 'c7c5',
        eval_cp: -20,
        eval_mate: null,
        explanation: 'e5 is solid, just 25 cp under the best line.',
        opening_eco: 'C20',
        opening_name: "King's Pawn Game",
        in_book: true,
        win_pct: 50,
      },
    ],
    eval_graph: [
      { ply: 1, cp: 20, mate: null },
      { ply: 2, cp: -20, mate: null },
    ],
    improvements: [
      { ply: 2, san: 'e5', color: 'b', best_uci: 'c7c5', loss_cp: 25 },
      { ply: 4, san: 'Nf6', color: 'w', best_uci: 'd2d4', loss_cp: 210 },
    ],
    ...overrides,
  };
}

function renderReview(
  path = '/games/7/review',
  voices: VoiceOption[] = [],
  prefs: VoicePreferences = { voice_authorized: false, voice_id: '' },
) {
  const user = userEvent.setup();
  vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', points: 0 });
  // The narration voice picker loads the free catalog + stored preference on
  // mount; both are defaulted here so no test reaches the network, and the
  // picker tests pass an explicit catalog to exercise the ElevenLabs options.
  vi.spyOn(api, 'listVoices').mockResolvedValue({ voices });
  vi.spyOn(api, 'getVoicePrefs').mockResolvedValue(prefs);
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/games/:id/review" element={<ReviewPage />} />
          <Route path="/games/:id" element={<p>Game page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
  return { user, ...view };
}

describe('ReviewPage loading (REVIEW-001/005)', () => {
  it('serves a stored review without re-analysing', async () => {
    const get = vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const create = vi.spyOn(api, 'createGameReview');
    renderReview();

    expect(await screen.findByText(/report card/)).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith(7);
    expect(create).not.toHaveBeenCalled();
  });

  it('generates one when none exists yet (409 from the cache read)', async () => {
    vi.spyOn(api, 'getGameReview').mockRejectedValue(new ApiError(409, 'No review exists yet'));
    const create = vi.spyOn(api, 'createGameReview').mockResolvedValue(review());
    renderReview();

    expect(
      await screen.findAllByText('e4 is exactly what the engine wants. Well played.'),
    ).toHaveLength(2); // the tour opens on move 1, so the board and the list agree
    expect(create).toHaveBeenCalledWith(7);
  });

  it('surfaces a failed analysis instead of an empty board', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(
      review({ status: 'failed', error: 'Stockfish binary not found', moves: [], eval_graph: [] }),
    );
    renderReview();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Stockfish binary not found');
  });

  it('rejects a non-numeric game id without fetching', async () => {
    const get = vi.spyOn(api, 'getGameReview');
    renderReview('/games/abc/review');
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid game id.');
    expect(get).not.toHaveBeenCalled();
  });

  it('shows the animated replay board while analysing, not a bare text card', async () => {
    // A review that never resolves keeps the page in its loading branch.
    let settle!: (value: ReviewResponse) => void;
    vi.spyOn(api, 'getGameReview').mockReturnValue(new Promise((resolve) => (settle = resolve)));
    // The thinking loader pulls the game to replay it backwards.
    vi.spyOn(api, 'getGame').mockResolvedValue({
      id: 7,
      mode: 'computer',
      status: 'active',
      fen: AFTER_E4,
      version: 2,
      moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }],
    });
    renderReview();

    // A live board is on screen while it thinks (not just a status paragraph).
    expect(await screen.findByRole('grid')).toBeInTheDocument();
    expect(screen.getByText(/Stockfish is replaying/)).toBeInTheDocument();
    settle(review()); // resolve the pending promise so nothing dangles
  });
});

describe('ReviewPage content (REVIEW-003/004)', () => {
  it('lists every ply with its grade and coaching line', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview();

    const list = await screen.findByRole('list', { name: 'classified moves' });
    expect(within(list).getAllByRole('button')).toHaveLength(2);
    expect(within(list).getByText('★')).toBeInTheDocument(); // the 'best' glyph
    expect(
      within(list).getByText('e5 is solid, just 25 cp under the best line.'),
    ).toBeInTheDocument();
  });

  it('jumps the board to the clicked ply', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const { user } = renderReview();

    const list = await screen.findByRole('list', { name: 'classified moves' });
    const pawnOnE4 = () => screen.getByRole('gridcell', { name: /^e4,/ });

    // The tour opens on ply 1, which is played from the start position: e4 empty.
    expect(pawnOnE4()).toHaveAccessibleName('e4, empty');

    // Ply 2 begins after e4, so the pawn is there.
    await user.click(within(list).getByText('e5'));
    expect(pawnOnE4()).toHaveAccessibleName('e4, white p');

    // Back to the first move replays the start position again.
    await user.click(within(list).getByText('e4'));
    expect(pawnOnE4()).toHaveAccessibleName('e4, empty');
  });

  it('shows only the reviewed player\u2019s improvements', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview();

    const card = await screen.findByText('Where to improve');
    const section = card.closest('div.card') as HTMLElement;
    // Hero is White: only the white ply-4 mistake is listed, not black e5.
    expect(within(section).getByText('Nf6')).toBeInTheDocument();
    expect(within(section).queryByText('e5')).not.toBeInTheDocument();
  });

  it('opens the coach assistant from the star, without disturbing the board tour', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const ask = vi.spyOn(api, 'askCoach').mockResolvedValue({
      answer: 'Your e5 slipped just under the best line.',
      intent: 'explain',
      mode: 'deterministic',
      provider: 'stockfish+book',
      references: [{ ply: 2, san: 'e5', color: 'b', note: 'a hair off best' }],
      position_fen: AFTER_E4,
    });
    const { user } = renderReview();

    // The panel is opt-in: the coach is absent until the star is pressed.
    expect(screen.queryByRole('region', { name: 'coach assistant' })).not.toBeInTheDocument();

    await user.click(await screen.findByRole('button', { name: 'Coach assistant' }));
    await screen.findByRole('region', { name: 'coach assistant' });

    await user.type(screen.getByLabelText('Ask the coach about this game'), 'why?');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    expect(
      await screen.findByText('Your e5 slipped just under the best line.'),
    ).toBeInTheDocument();
    // The board cursor (ply 1 at the tour start) is what the coach is told to focus on.
    expect(ask).toHaveBeenCalledWith(7, { question: 'why?', focus_ply: 1, history: [] });
  });

  it('walks a coach-suggested line on the main board, then returns to the game', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    vi.spyOn(api, 'askCoach').mockResolvedValue({
      answer: 'The line: e5.',
      intent: 'lesson',
      mode: 'deterministic',
      provider: 'stockfish+book',
      references: [{ ply: 2, san: 'e5', color: 'b', note: '' }],
      position_fen: AFTER_E4,
      line_title: "The engine's line",
      line: [
        {
          san: 'e5',
          uci: 'e7e5',
          color: 'b',
          fen_before: AFTER_E4,
          fen_after: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2',
          comment: 'engine: +0.20',
          source: 'engine',
          ply: null,
        },
      ],
    });
    const { user } = renderReview();

    const pawnOnE5 = () => screen.getByRole('gridcell', { name: /^e5,/ });
    // Tour opens on ply 1 (played from the start): e5 is empty.
    await screen.findByText('Move 1 of 2');
    expect(pawnOnE5()).toHaveAccessibleName('e5, empty');

    await user.click(await screen.findByRole('button', { name: 'Coach assistant' }));
    await user.type(screen.getByLabelText('Ask the coach about this game'), 'show me the line');
    await user.click(screen.getByRole('button', { name: 'Send question' }));

    await user.click(await screen.findByRole('button', { name: /Show this line on the board/i }));

    // The big board now walks the variation, not the game.
    expect(await screen.findByText("The engine's line")).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 1')).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'lesson navigation' })).toBeInTheDocument();
    expect(pawnOnE5()).toHaveAccessibleName('e5, black p');

    // Exiting snaps back to the recorded tour.
    await user.click(screen.getByRole('button', { name: 'Exit lesson' }));
    expect(await screen.findByText('Move 1 of 2')).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'move navigation' })).toBeInTheDocument();
    expect(pawnOnE5()).toHaveAccessibleName('e5, empty');
  });

  it('re-analyses on demand', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const create = vi.spyOn(api, 'createGameReview').mockResolvedValue(review());
    const { user } = renderReview();

    await user.click(await screen.findByRole('button', { name: /Re-analyse/ }));
    expect(create).toHaveBeenCalledWith(7, { force: true });
  });
});

describe('ReviewPage tour (REVIEW-007/008/009)', () => {
  /** jsdom has no speech engine, so the tests lend the page one it can hear. */
  function installSpeech() {
    const texts: string[] = [];
    const cancel = vi.fn();
    Object.defineProperty(window, 'speechSynthesis', {
      configurable: true,
      value: { cancel, getVoices: () => [], speak: (u: { text: string }) => texts.push(u.text) },
    });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', {
      configurable: true,
      value: class {
        text: string;
        rate = 1;
        pitch = 1;
        volume = 1;
        lang = '';
        voice: unknown = null;
        onerror: (() => void) | null = null;

        constructor(text: string) {
          this.text = text;
        }
      },
    });
    return { texts, cancel };
  }

  function removeSpeech() {
    const win = window as unknown as Record<string, unknown>;
    delete win.speechSynthesis;
    delete win.SpeechSynthesisUtterance;
  }

  afterEach(() => {
    removeSpeech();
    cleanup();
  });

  it('opens the replay on the first move and counts the plies', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview();

    expect(await screen.findByText('Move 1 of 2')).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'move navigation' })).toBeInTheDocument();
  });

  it('walks forward and backward and stops at both bounds', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const { user } = renderReview();

    await screen.findByText('Move 1 of 2');
    const first = screen.getByRole('button', { name: 'First move' });
    const prev = screen.getByRole('button', { name: 'Previous move' });
    const next = screen.getByRole('button', { name: 'Next move' });
    const last = screen.getByRole('button', { name: 'Last move' });

    // Nothing earlier than the first move: the tour cannot walk off the game.
    expect(first).toBeDisabled();
    expect(prev).toBeDisabled();

    await user.click(next);
    expect(screen.getByText('Move 2 of 2')).toBeInTheDocument();
    expect(next).toBeDisabled();
    expect(last).toBeDisabled();

    await user.click(last); // already last, and inert rather than an error
    await user.click(prev);
    expect(screen.getByText('Move 1 of 2')).toBeInTheDocument();

    await user.click(next);
    await user.click(first);
    expect(screen.getByText('Move 1 of 2')).toBeInTheDocument();
  });

  it('walks the plies with the arrow keys', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview();

    await screen.findByText('Move 1 of 2');
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(await screen.findByText('Move 2 of 2')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'ArrowLeft' });
    expect(await screen.findByText('Move 1 of 2')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'End' });
    expect(await screen.findByText('Move 2 of 2')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'Home' });
    expect(await screen.findByText('Move 1 of 2')).toBeInTheDocument();

    // An unrelated key must not move the board.
    fireEvent.keyDown(window, { key: 'ArrowDown' });
    expect(screen.getByText('Move 1 of 2')).toBeInTheDocument();
  });

  it('ignores arrow keys while a modifier is held', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview();

    await screen.findByText('Move 1 of 2');
    fireEvent.keyDown(window, { key: 'ArrowRight', ctrlKey: true });
    expect(screen.getByText('Move 1 of 2')).toBeInTheDocument();
  });

  it('names the opening, the book state and the expectancy of the shown ply', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview();

    const card = (await screen.findByText('Opening and odds')).closest('div.card') as HTMLElement;
    expect(within(card).getByText('B00')).toBeInTheDocument();
    expect(within(card).getByText("King's Pawn Game")).toBeInTheDocument();
    expect(within(card).getByText('In book')).toBeInTheDocument();
    expect(within(card).getByText(/engine win expectancy here/)).toHaveTextContent('76%');
    // Both plies of this game are inside the same opening family.
    expect(within(card).getByText(/Across this opening in this game, about 63%/));
    // ...and the panel says plainly that this is the engine's number.
    expect(within(card).getByText(/not a win rate copied from other/)).toBeInTheDocument();
  });

  it('reads the expectancy from the reviewed player\u2019s own side', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review({ hero_color: 'b' }));
    renderReview();

    const card = (await screen.findByText('Opening and odds')).closest('div.card') as HTMLElement;
    // White was 76% up, so the player being coached is at 24%.
    expect(within(card).getByText(/engine win expectancy here/)).toHaveTextContent('24%');
    expect(
      within(card).getByText(/Across this opening in this game, about 37%/),
    ).toBeInTheDocument();
  });

  it('says so when the position is outside the book', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(
      review({
        moves: review().moves.map((m) => ({
          ...m,
          opening_eco: null,
          opening_name: null,
          in_book: false,
        })),
      }),
    );
    renderReview();

    expect(await screen.findByText(/outside the theory book/)).toBeInTheDocument();
    expect(screen.queryByText('In book')).not.toBeInTheDocument();
  });

  it('narrates a step, not the automatic landing on move one', async () => {
    const { texts } = installSpeech();
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const { user } = renderReview();

    await screen.findByText('Move 1 of 2');
    expect(texts).toEqual([]);

    await user.click(screen.getByRole('button', { name: 'Next move' }));
    const spoken = texts.join(' ');
    expect(spoken).toContain('Black plays pawn to e5');
    expect(spoken).toContain("This is King's Pawn Game.");
    expect(spoken).toContain('25 points under the best line');
    expect(spoken).not.toContain(' cp ');
  });

  it('holds its tongue when the voice preference is off', async () => {
    const { texts } = installSpeech();
    vi.spyOn(settings, 'getPref').mockReturnValue(false);
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const { user } = renderReview();

    await screen.findByText('Move 1 of 2');
    await user.click(screen.getByRole('button', { name: 'Next move' }));
    expect(screen.getByText('Move 2 of 2')).toBeInTheDocument();
    expect(texts).toEqual([]);
  });

  it('shows the voice toggle even without speechSynthesis (TTS is always an option)', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    // Without speechSynthesis: fetch exists, so voiceAvailable() is true (TTS path).
    const withoutSpeech = renderReview();
    await withoutSpeech.findByText('Move 1 of 2');
    expect(screen.getByRole('button', { name: /voice on|voice off/i })).toBeInTheDocument();
    withoutSpeech.unmount();
    cleanup();

    installSpeech();
    const withSpeech = renderReview();
    await withSpeech.findByText('Move 1 of 2');
    expect(screen.getByRole('button', { name: /voice on/i })).toBeInTheDocument();
  });

  it('stops the narrator when the review page goes away', async () => {
    const { cancel } = installSpeech();
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const { user } = renderReview();

    await screen.findByText('Move 1 of 2');
    await user.click(screen.getByRole('button', { name: 'Next move' }));
    cancel.mockClear();

    cleanup();
    expect(cancel).toHaveBeenCalled();
  });
});

describe('ReviewPage narration voice picker (REVIEW-009)', () => {
  afterEach(() => cleanup());

  it('leads with an ElevenLabs free voice (Adam) and offers only ElevenLabs', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    const { user } = renderReview('/games/7/review', [
      { id: 'pNInz6obpgDQGcFmaJgB', name: 'Adam', engine: 'eleven', available: true },
      { id: 'JBFqnCBsd6RMkjVDRZzb', name: 'George', engine: 'eleven', available: true },
    ]);

    // Adam is the main narrator even with no stored preference.
    const trigger = await screen.findByRole('button', { name: 'Review narration voice' });
    expect(within(trigger).getByText('Adam')).toBeInTheDocument();

    await user.click(trigger);
    const menu = await screen.findByRole('listbox', { name: 'Review narration voice' });
    expect(within(menu).getByRole('option', { name: /George/ })).toBeInTheDocument();
    // The review picker never lists browser voices or a "system default" reset.
    expect(within(menu).queryByText('Browser voices')).not.toBeInTheDocument();
    expect(within(menu).queryByRole('option', { name: /System default/ })).not.toBeInTheDocument();

    // Picking a free voice applies it to the narrator and persists it (REVIEW-009).
    const save = vi.spyOn(api, 'saveVoicePrefs').mockResolvedValue({
      voice_authorized: false,
      voice_id: 'JBFqnCBsd6RMkjVDRZzb',
    });
    await user.click(within(menu).getByRole('option', { name: /George/ }));
    expect(save).toHaveBeenCalledWith({ voice_id: 'JBFqnCBsd6RMkjVDRZzb' });
    expect(
      screen.queryByRole('listbox', { name: 'Review narration voice' }),
    ).not.toBeInTheDocument();
    expect(within(trigger).getByText('George')).toBeInTheDocument();
  });

  it('marks a free voice unavailable when no key is configured', async () => {
    vi.spyOn(api, 'getGameReview').mockResolvedValue(review());
    renderReview('/games/7/review', [
      { id: 'pNInz6obpgDQGcFmaJgB', name: 'Adam', engine: 'eleven', available: false },
    ]);

    const trigger = await screen.findByRole('button', { name: 'Review narration voice' });
    fireEvent.click(trigger);
    const option = await screen.findByRole('option', { name: /Adam/ });
    expect(option).toBeDisabled();
  });
});
