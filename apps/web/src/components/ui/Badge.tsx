import { type HTMLAttributes } from 'react';

export type BadgeProps = HTMLAttributes<HTMLDivElement> & {
  name: string;
  desc: string;
  icon: string;
  unlocked?: boolean;
};

export function Badge({ name, desc, icon, unlocked = true, className }: BadgeProps) {
  return (
    <div className={`badge-card ${unlocked ? '' : 'locked'} ${className}`}>
      <div className="badge-icon">{icon}</div>
      <div className="badge-name">{name}</div>
      <div className="badge-desc">{desc}</div>
    </div>
  );
}
