import { type HTMLAttributes } from 'react';

export type CardProps = HTMLAttributes<HTMLDivElement>;

export function Card({ className, children, ...props }: CardProps) {
  return (
    <div className={`panel-card ${className ?? ''}`} {...props}>
      {children}
    </div>
  );
}
