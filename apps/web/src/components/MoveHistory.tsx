/** Move history list with numbering (WEB-017), empty state included. */
import { motion } from 'framer-motion';
import type { MoveResponse } from '../lib/api-types';

export default function MoveHistory({ moves }: { moves: MoveResponse[] }) {
  if (moves.length === 0) {
    return (
      <div className="empty-state">
        <p>No moves yet. White to move.</p>
      </div>
    );
  }
  const rows: { num: number; white?: string; black?: string }[] = [];
  moves.forEach((m, idx) => {
    if (idx % 2 === 0) rows.push({ num: idx / 2 + 1, white: m.san });
    else rows[rows.length - 1].black = m.san;
  });
  return (
    <ol aria-label="move history" className="moves-list">
      {rows.map((row, idx) => (
        <motion.li
          key={row.num}
          className={['move-row', idx === rows.length - 1 ? 'move-last' : '']
            .filter(Boolean)
            .join(' ')}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
        >
          <span className="move-number">{row.num}.</span>
          <span>{row.white}</span>
          {row.black && (
            <>
              {' '}
              <span>{row.black}</span>
            </>
          )}
        </motion.li>
      ))}
    </ol>
  );
}
