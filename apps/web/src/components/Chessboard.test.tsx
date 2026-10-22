import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import Chessboard from './Chessboard';

const STARTING = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

function renderBoard() {
  const onSelect = vi.fn();
  const onMove = vi.fn();
  render(
    <Chessboard
      fen={STARTING}
      status="active"
      selected={null}
      onSelect={onSelect}
      onMove={onMove}
    />,
  );
  return { onSelect, onMove };
}

describe('Chessboard accessibility grid (WEB-027)', () => {
  it('exposes an 8x8 grid of rows and cells', () => {
    renderBoard();
    expect(screen.getAllByRole('row')).toHaveLength(8);
    expect(screen.getAllByRole('gridcell')).toHaveLength(64);
  });

  it('moves focus with the arrow keys', () => {
    renderBoard();
    const a2 = screen.getByRole('gridcell', { name: /^a2,/ });
    a2.focus();
    fireEvent.keyDown(a2, { key: 'ArrowRight' });
    expect(document.activeElement).toBe(screen.getByRole('gridcell', { name: /^b2,/ }));
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'ArrowUp' });
    expect(document.activeElement).toBe(screen.getByRole('gridcell', { name: /^b3,/ }));
  });

  it('keeps a single roving tab stop', () => {
    renderBoard();
    const tabbable = screen
      .getAllByRole('gridcell')
      .filter((cell) => cell.getAttribute('tabindex') === '0');
    expect(tabbable).toHaveLength(1);
  });

  it('selects a piece on Enter', () => {
    const { onSelect } = renderBoard();
    fireEvent.keyDown(screen.getByRole('gridcell', { name: /^a2,/ }), { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('a2');
  });
});
