import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../app/AuthContext';
import { ApiError, api } from '../lib/api-client';
import type { GameResponse } from '../lib/api-types';
import GamePage from './GamePage';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1';

function game(overrides: Partial<GameResponse> = {}): GameResponse {
  return {
    id: 7,
    mode: 'local',
    status: 'active',
    fen: START_FEN,
    version: 1,
    player_color: 'white',
    engine_level: 'medium',
    result: '*',
    winner: null,
    end_reason: null,
    in_check: false,
    move_count: 0,
    moves: [],
    ...overrides,
  };
}

function renderGame(path = '/games/7') {
  const user = userEvent.setup();
  vi.spyOn(api, 'me').mockResolvedValue({ id: 1, email: 'a@b.co', email_verified: true });
  // Each test spies `getGame` before calling this so load states are explicit.
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/games/:id" element={<GamePage />} />
          <Route path="/" element={<p>Dashboard</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
  return { user, ...view };
}

/**
 * Click a source square then a destination square. Squares are `gridcell`
 * buttons inside a `grid`, so the explicit role is required.
 */
async function clickMove(user: ReturnType<typeof userEvent.setup>, from: string, to: string) {
  await user.click(await screen.findByRole('gridcell', { name: new RegExp(`^${from},`) }));
  await user.click(screen.getByRole('gridcell', { name: new RegExp(`^${to},`) }));
}

describe('GamePage load (WEB-024/025)', () => {
  it('rejects a non-numeric game id without fetching', async () => {
    const getGame = vi.spyOn(api, 'getGame');
    renderGame('/games/not-a-number');

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid game id.');
    expect(getGame).not.toHaveBeenCalled();
  });

  it('resumes an existing game from the API', async () => {
    const resumed = game({
      fen: AFTER_E4,
      version: 2,
      moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }],
    });
    const getGame = vi.spyOn(api, 'getGame').mockResolvedValue(resumed);
    renderGame('/games/7');

    expect(await screen.findByRole('heading', { name: /Game #7/ })).toBeInTheDocument();
    expect(getGame).toHaveBeenCalledWith(7);
    expect(screen.getByRole('list', { name: 'move history' })).toHaveTextContent('e4');
    // Board reflects the resumed position: e4 occupied, e2 empty.
    expect(screen.getByRole('gridcell', { name: /^e4,/ })).toHaveTextContent('♙');
    expect(screen.getByRole('gridcell', { name: /^e2,/ })).not.toHaveTextContent('♙');
  });

  it('shows an error state when the game cannot be loaded', async () => {
    vi.spyOn(api, 'getGame').mockRejectedValueOnce(new ApiError(404, 'Game not found'));
    renderGame('/games/7');

    expect(await screen.findByRole('alert')).toHaveTextContent('Game not found');
    expect(screen.getByRole('link', { name: /dashboard/i })).toBeInTheDocument();
  });
});

describe('GamePage moves (WEB-011/019/025)', () => {
  it('submits a click-to-move with the expected version', async () => {
    const submit = vi
      .spyOn(api, 'submitMove')
      .mockResolvedValue(
        game({ fen: AFTER_E4, version: 2, moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }] }),
      );
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e4');

    expect(submit).toHaveBeenCalledWith(7, { uci: 'e2e4', expected_version: 1 });
    expect(await screen.findByRole('list', { name: 'move history' })).toHaveTextContent('e4');
  });

  it('surfaces an illegal move as an error without changing the board', async () => {
    vi.spyOn(api, 'submitMove').mockRejectedValueOnce(new ApiError(422, 'Illegal move'));
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e5');

    expect(await screen.findByRole('alert')).toHaveTextContent('Illegal move');
    // Board unchanged: pawn still on e2.
    expect(screen.getByRole('gridcell', { name: /^e2,/ })).toHaveTextContent('♙');
  });

  it('re-syncs the board after a 409 version conflict', async () => {
    vi.spyOn(api, 'submitMove').mockRejectedValueOnce(new ApiError(409, 'Game changed'));
    // First call is the mount, second is the conflict refetch (WEB-025).
    const getGame = vi
      .spyOn(api, 'getGame')
      .mockResolvedValueOnce(game())
      .mockResolvedValueOnce(game({ fen: AFTER_E4, version: 5 }));
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e4');

    expect(await screen.findByRole('alert')).toHaveTextContent('Game changed');
    await waitFor(() => expect(getGame).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByRole('gridcell', { name: /^e4,/ })).toHaveTextContent('♙'),
    );
  });

  it('undoes a move', async () => {
    const undo = vi.spyOn(api, 'undoMove').mockResolvedValue(game({ version: 3 }));
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ version: 4, moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }] }),
    );
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: 'Undo' }));

    expect(undo).toHaveBeenCalledWith(7, { expected_version: 4 });
  });

  it('resigns the game and locks the controls', async () => {
    vi.spyOn(api, 'resignGame').mockResolvedValue(game({ status: 'resigned', version: 2 }));
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: 'Resign' }));

    expect(await screen.findByText(/Resigned/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resign' })).toBeDisabled();
  });

  it('resets to the start by undoing every move', async () => {
    const undo = vi
      .spyOn(api, 'undoMove')
      // Each undo removes one move from the server's view.
      .mockResolvedValueOnce(
        game({
          version: 3,
          moves: [
            { uci: 'e2e4', san: 'e4', move_number: 1 },
            { uci: 'e7e5', san: 'e5', move_number: 1 },
          ],
        }),
      )
      .mockResolvedValueOnce(
        game({ version: 2, moves: [{ uci: 'e2e4', san: 'e4', move_number: 1 }] }),
      )
      .mockResolvedValue(game({ version: 1, moves: [] }));
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({
        version: 4,
        moves: [
          { uci: 'e2e4', san: 'e4', move_number: 1 },
          { uci: 'e7e5', san: 'e5', move_number: 1 },
          { uci: 'g1f3', san: 'Nf3', move_number: 2 },
        ],
      }),
    );
    const { user } = renderGame('/games/7');

    await user.click(await screen.findByRole('button', { name: /Reset to start/ }));

    expect(undo).toHaveBeenCalledTimes(3);
    await waitFor(() => expect(undo).toHaveBeenLastCalledWith(7, { expected_version: 2 }));
    // Empty move list renders the empty state, not the <ol>.
    expect(await screen.findByText('No moves yet. White to move.')).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'move history' })).not.toBeInTheDocument();
  });
});

describe('GamePage promotion (WEB-015)', () => {
  it('asks which piece to promote to before sending the move', async () => {
    const submit = vi.spyOn(api, 'submitMove').mockResolvedValue(game({ version: 2 }));
    // White pawn on b7 ready to promote on a8.
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ fen: '1nb1kbn1/1P1ppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' }),
    );
    const { user } = renderGame('/games/7');

    await clickMove(user, 'b7', 'a8');

    // Picker appears before any request is sent.
    const dialog = await screen.findByRole('dialog');
    expect(submit).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole('button', { name: /promote to n/i }));

    expect(submit).toHaveBeenCalledWith(7, { uci: 'b7a8n', expected_version: 1 });
  });
});

describe('GamePage status and result banner (WEB-013/014)', () => {
  it('announces checkmate as game over and locks controls', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({
        status: 'checkmate',
        result: '0-1',
        winner: 'black',
        end_reason: 'checkmate',
        fen: 'rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3',
      }),
    );
    renderGame('/games/7');

    expect(await screen.findByText(/Checkmate/)).toBeInTheDocument();
    // The banner shows the real result, phrased from White's (player) view.
    expect(screen.getByText(/you lost/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resign' })).toBeDisabled();
  });

  it('announces stalemate as a draw', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({ status: 'stalemate', result: '1/2-1/2', fen: 'k7/8/1Q6/8/8/8/8/K7 b - - 0 1' }),
    );
    renderGame('/games/7');

    expect(await screen.findByText(/Stalemate/)).toBeInTheDocument();
    expect(screen.getByText(/Result: draw/)).toBeInTheDocument();
  });

  it('renders a check flag from the server in_check field, not the FEN', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(
      game({
        fen: 'rnbqkbnr/pppp1ppp/8/4p3/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 2',
        in_check: true,
      }),
    );
    renderGame('/games/7');

    expect(await screen.findByText(/check!/)).toBeInTheDocument();
  });
});

describe('GamePage computer auto-reply (Phase 3)', () => {
  it('has no manual engine-move button', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'computer' }));
    renderGame('/games/7');

    await screen.findByRole('heading', { name: /Game #7/ });
    expect(screen.queryByRole('button', { name: /Engine move/i })).not.toBeInTheDocument();
  });

  it('renders the engine reply from the single move response', async () => {
    // A human e2e4 plus Stockfish's e7e5 come back together in one response.
    const submit = vi.spyOn(api, 'submitMove').mockResolvedValue(
      game({
        mode: 'computer',
        fen: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',
        version: 3,
        move_count: 2,
        moves: [
          { uci: 'e2e4', san: 'e4', move_number: 1 },
          { uci: 'e7e5', san: 'e5', move_number: 1 },
        ],
      }),
    );
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'computer', player_color: 'white' }));
    const { user } = renderGame('/games/7');

    await clickMove(user, 'e2', 'e4');

    expect(submit).toHaveBeenCalledWith(7, { uci: 'e2e4', expected_version: 1 });
    const history = await screen.findByRole('list', { name: 'move history' });
    expect(history).toHaveTextContent('e4');
    expect(history).toHaveTextContent('e5');
  });

  it('orients the board for a Black player', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(game({ mode: 'computer', player_color: 'black' }));
    renderGame('/games/7');
    await screen.findByRole('heading', { name: /Game #7/ });

    // Flipped: the top-left cell is h1 and the bottom-right is a8.
    const cells = screen.getAllByRole('gridcell');
    expect(cells[0]).toHaveAccessibleName(/^h1,/);
    expect(cells[cells.length - 1]).toHaveAccessibleName(/^a8,/);
  });

  it('offers a PGN download for the game', async () => {
    vi.spyOn(api, 'getGame').mockResolvedValue(game());
    renderGame('/games/7');

    const link = await screen.findByRole('link', { name: /Download PGN/i });
    expect(link).toHaveAttribute('href', expect.stringContaining('/api/v1/games/7/pgn'));
  });
});
