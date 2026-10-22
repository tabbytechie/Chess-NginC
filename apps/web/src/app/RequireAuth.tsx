/** Route guard: redirects unauthenticated users to /login. */
import { Navigate, useLocation } from 'react-router-dom';

import { EmailVerifyBanner } from '../components/EmailVerifyBanner';
import { useAuth } from './useAuth';
import type { ReactNode } from 'react';

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p role="status">Loading…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return (
    <>
      <EmailVerifyBanner />
      {children}
    </>
  );
}
