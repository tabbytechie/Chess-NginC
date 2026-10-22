/** Status banner: check/checkmate/stalemate/draw/resigned (WEB-015/016). */
import type { GameResult, GameStatus as Status, PlayerColor } from '../lib/api-types';

const LABELS: Record<Status, string> = {
  active: 'Game in progress',
  checkmate: 'Checkmate — game over',
  stalemate: 'Stalemate — draw',
  draw: 'Draw',
  resigned: 'Resigned — game over',
  abandoned: 'Abandoned',
};

const STATUS_VARIANTS: Record<Status, string> = {
  active: 'game-status active',
  checkmate: 'game-status checkmate',
  stalemate: 'game-status stalemate',
  draw: 'game-status draw',
  resigned: 'game-status resigned',
  abandoned: 'game-status resigned',
};

/** Human-readable result line keyed by the PGN token and the player's side. */
function resultText(
  result: GameResult,
  winner: PlayerColor | null | undefined,
  playerColor: PlayerColor,
): string | null {
  if (result === '*') return null;
  if (result === '1/2-1/2') return 'Result: draw (½–½)';
  const won = winner === playerColor;
  return won ? `Result: ${result} — you won!` : `Result: ${result} — you lost`;
}

export default function GameStatusBanner({
  status,
  inCheck,
  result = '*',
  winner = null,
  playerColor = 'white',
}: {
  status: Status;
  inCheck: boolean;
  result?: GameResult;
  winner?: PlayerColor | null;
  playerColor?: PlayerColor;
}) {
  const outcome = status === 'active' ? null : resultText(result, winner, playerColor);
  return (
    <div role="status" aria-live="polite" className={STATUS_VARIANTS[status]}>
      <strong>{LABELS[status]}</strong>
      {status === 'active' && inCheck && <span> — check!</span>}
      {outcome && <span className="game-result"> — {outcome}</span>}
    </div>
  );
}
