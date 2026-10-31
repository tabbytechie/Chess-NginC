/**
 * Account menu: avatar + points chip + email trigger with a dropdown holding
 * the dashboard link and log out (logout no longer sits in the dashboard hero).
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronDown, Coins, LayoutDashboard, LogOut } from 'lucide-react';

import { useAuth } from '../app/useAuth';

export default function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  if (!user) return null;

  async function handleLogout() {
    setOpen(false);
    await logout();
    // Signed out, `/` is the landing descent — leave visitors at the front
    // door, not at the login form.
    navigate('/', { replace: true });
  }

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        className="user-menu-button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="user-avatar" aria-hidden="true">
          {user.email[0].toUpperCase()}
        </span>
        <span className="points-chip" title="Points earned">
          <Coins size={13} aria-hidden="true" />
          {user.points.toLocaleString()}
          <span className="sr-only">points</span>
        </span>
        <span className="user-email">{user.email}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="menu-popover" role="menu">
          <p className="menu-heading">{user.email}</p>
          <p className="menu-points">
            <Coins size={14} aria-hidden="true" />
            {user.points.toLocaleString()} points earned
          </p>
          <div className="menu-separator" />
          <Link to="/" role="menuitem" className="menu-item" onClick={() => setOpen(false)}>
            <LayoutDashboard size={15} aria-hidden="true" />
            Dashboard
          </Link>
          <button type="button" role="menuitem" className="menu-item danger" onClick={handleLogout}>
            <LogOut size={15} aria-hidden="true" />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
