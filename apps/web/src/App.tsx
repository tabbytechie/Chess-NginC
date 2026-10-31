/**
 * Application shell and routes (WEB-004).
 * Public: / (landing descent for signed-out visitors), /login, /register,
 * /forgot-password, /reset-password.
 * Protected: dashboard + game pages.
 * Header: brand + nav left, theme switcher and account menu right;
 * logout lives in the account menu, not in page content. The landing page
 * owns its own nav, so the app header and footer step aside for it.
 * RB-006: the four pages behind top-level navigation are code-split; the
 * dashboard's first paint no longer pays for the review/coach/drill UI.
 */
import { Suspense, lazy, type ReactNode } from 'react';
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom';

import RequireAuth from './app/RequireAuth';
import { useAuth } from './app/useAuth';
import ThemeToggle from './components/ThemeToggle';
import UserMenu from './components/UserMenu';
import LandingPage from './landing/LandingPage';
import Dashboard from './pages/Dashboard';
import GamePage from './pages/GamePage';
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from './pages/AuthPages';

const AchievementsPage = lazy(() => import('./pages/AchievementsPage'));
const LearnPage = lazy(() => import('./pages/LearnPage'));
const LobbyPage = lazy(() => import('./pages/LobbyPage'));
const OnlineGamePage = lazy(() => import('./pages/OnlineGamePage'));
const ReviewPage = lazy(() => import('./pages/ReviewPage'));

function RouteFallback() {
  // Distinct from AuthContext's "Loading…" (session restoration) so the two
  // waiting states never read as each other.
  return <div className="loading-state">Loading page…</div>;
}

/**
 * `/` is the marketing landing descent for signed-out visitors and the
 * dashboard for signed-in ones; the session-restoration wait keeps the
 * RequireAuth "Loading…" wording so the two loading states stay identical.
 */
function HomeRoute() {
  const { user, loading } = useAuth();
  if (loading) return <p role="status">Loading…</p>;
  if (!user) return <LandingPage />;
  return <Dashboard />;
}

function guarded(node: ReactNode) {
  return (
    <RequireAuth>
      <Suspense fallback={<RouteFallback />}>{node}</Suspense>
    </RequireAuth>
  );
}

function Header() {
  const { user } = useAuth();
  return (
    <header className="app-header">
      <div className="header-inner">
        <Link to="/" className="brand" aria-label="Chess NginC home">
          <span className="brand-mark" aria-hidden="true">
            ♞
          </span>
          <span>
            <span className="brand-name">Chess NginC</span>
            <span className="brand-tag">Play · Improve · Compete</span>
          </span>
        </Link>
        {user && (
          <nav className="header-nav" aria-label="primary">
            <NavLink
              to="/"
              end
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              Home
            </NavLink>
            <NavLink
              to="/lobby"
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              Play online
            </NavLink>
            <NavLink
              to="/learn"
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              Learn
            </NavLink>
            <NavLink
              to="/achievements"
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              Achievements
            </NavLink>
          </nav>
        )}
        <div className="header-actions">
          <ThemeToggle />
          {user ? (
            <UserMenu />
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost btn-small">
                Log in
              </Link>
              <Link to="/register" className="btn btn-primary btn-small">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  const location = useLocation();
  // The landing owns its own nav and ends on the finale scene — no app
  // header, no footer while it is on screen.
  const landing = location.pathname === '/' && !loading && !user;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {!landing && <Header />}
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/" element={<HomeRoute />} />
        <Route
          path="/games/:id"
          element={
            <RequireAuth>
              <GamePage />
            </RequireAuth>
          }
        />
        <Route path="/games/:id/review" element={guarded(<ReviewPage />)} />
        <Route path="/achievements" element={guarded(<AchievementsPage />)} />
        <Route path="/learn" element={guarded(<LearnPage />)} />
        <Route path="/lobby" element={guarded(<LobbyPage />)} />
        <Route path="/online/:id" element={guarded(<OnlineGamePage />)} />
        <Route
          path="*"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
      </Routes>
      {!landing && <footer className="app-footer">Chess NginC — play the position, not the clock.</footer>}
    </div>
  );
}
