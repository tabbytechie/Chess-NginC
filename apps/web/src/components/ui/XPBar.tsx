import { type HTMLAttributes } from 'react';

export type XPBarProps = HTMLAttributes<HTMLDivElement> & {
  level: number;
  xp: number;
  maxXp: number;
};

export function XPBar({ level, xp, maxXp, className }: XPBarProps) {
  const progress = Math.min(100, Math.max(0, Math.round((xp / maxXp) * 100)));

  return (
    <div className={`xp-container ${className}`}>
      <div className="xp-level-badge">
        <span>Level {level}</span>
      </div>
      <div className="xp-header">
        <span>XP</span>
        <span>
          {xp} / {maxXp}
        </span>
      </div>
      <div className="xp-bar">
        <div className="xp-progress" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
