/**
 * Application shell and routes (WEB-004).
 * Public: /login, /register, the recovery pages. Protected: dashboard + game.
 * Phase 6: GamePage is code-split behind `React.lazy`, so the board/game
 * bundle (and its animation dependency) is fetched only when a game is opened
 * rather than on the login and dashboard first paint.
 */
import { lazy, Suspense } from 'react';
import { Link, Route, Routes } from 'react-router-dom';

import RequireAuth from './app/RequireAuth';
import { useAuth } from './app/useAuth';
import Dashboard from './pages/Dashboard';
import { LoginPage, RegisterPage } from './pages/AuthPages';
import { ForgotPasswordPage, ResetPasswordPage, VerifyEmailPage } from './pages/RecoveryPages';

const GamePage = lazy(() => import('./pages/GamePage'));

function TopNav() {
  const { user } = useAuth();
  return (
    <header className="topnav">
      <Link to="/" className="brand-link" aria-label="Chess NginC home">
        <span className="brand-mark" aria-hidden="true">
          ♞
        </span>
        <span>
          Chess NginC
          <span className="brand-sub">Play · Battle · Flex</span>
        </span>
      </Link>
      <nav className="nav-links" aria-label="primary">
        {user ? (
          <span className="nav-email" title={user.email}>
            {user.email}
          </span>
        ) : (
          <>
            <Link to="/login" className="nav-pill">
              Log in
            </Link>
            <Link to="/register" className="nav-pill">
              Sign up
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <div className="bg-orbs" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <TopNav />
      <Suspense fallback={<p role="status">Loading…</p>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/games/:id"
            element={
              <RequireAuth>
                <GamePage />
              </RequireAuth>
            }
          />
          <Route
            path="*"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
        </Routes>
      </Suspense>
      <footer className="app-footer">Made for the next generation of grandmasters ♞</footer>
    </div>
  );
}
