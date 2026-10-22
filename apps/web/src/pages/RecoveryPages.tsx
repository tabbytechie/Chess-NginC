/**
 * Account-recovery pages (SEC-013). Public routes:
 *   /forgot-password  — request a reset link for an email
 *   /reset-password   — set a new password using the emailed `?token=`
 *   /verify-email     — confirm an address using the emailed `?token=`
 *
 * The request/reset/verify endpoints all return a uniform reply, so these forms
 * never reveal whether an account exists. A reset succeeds -> send the user to
 * log back in (all prior sessions were revoked server-side).
 */
import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { Button } from '../components/ui/Button';
import { ApiError, api } from '../lib/api-client';

const MIN_PASSWORD = 8;

function ErrorText({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="error">
      {children}
    </p>
  );
}

function InfoText({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="auth-note">
      {children}
    </p>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.requestPasswordReset({ email: email.trim() });
      // Uniform reply: always show the same "check your inbox" message.
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not process the request.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <div className="auth-card">
        <h1>Forgot password</h1>
        <p className="u-muted mb-lg">We&apos;ll email you a reset link</p>
        {sent ? (
          <InfoText>
            If that email is registered, a reset link is on its way. Check your inbox.
          </InfoText>
        ) : (
          <form onSubmit={onSubmit} aria-label="forgot password form">
            <div className="field">
              <label htmlFor="forgot-email">Email</label>
              <input
                id="forgot-email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            {error && <ErrorText>{error}</ErrorText>}
            <Button type="submit" variant="primary" disabled={busy} className="w-full">
              {busy ? 'Sending…' : 'Send reset link'}
            </Button>
          </form>
        )}
        <p className="mt-lg">
          <Link to="/login" className="text-neon-blue hover:text-neon-pink">
            Back to log in
          </Link>
        </p>
      </div>
    </main>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(
    !token ? 'This reset link is missing its token.' : null,
  );

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters.`);
      return;
    }
    setBusy(true);
    try {
      await api.resetPassword({ token, password });
      navigate('/login', {
        replace: true,
        state: { notice: 'Password reset. Please log in again.' },
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reset the password.');
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <main className="auth">
        <div className="auth-card">
          <h1>Reset password</h1>
          <ErrorText>{error ?? 'Invalid or expired link.'}</ErrorText>
          <p className="mt-lg">
            <Link to="/forgot-password" className="text-neon-blue hover:text-neon-pink">
              Request a new link
            </Link>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="auth">
      <div className="auth-card">
        <h1>Choose a new password</h1>
        <p className="u-muted mb-lg">For your security, this logs out every device</p>
        <form onSubmit={onSubmit} aria-label="reset password form">
          <div className="field">
            <label htmlFor="reset-password">New password (min {MIN_PASSWORD} characters)</label>
            <input
              id="reset-password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <ErrorText>{error}</ErrorText>}
          <Button type="submit" variant="brand" disabled={busy} className="w-full">
            {busy ? 'Saving…' : 'Reset password'}
          </Button>
        </form>
      </div>
    </main>
  );
}

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [status, setStatus] = useState<'pending' | 'ok' | 'bad'>(token ? 'pending' : 'bad');
  const [message, setMessage] = useState<string>(
    token ? '' : 'This verification link is missing its token.',
  );

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .verifyEmail({ token })
      .then((reply) => {
        if (cancelled) return;
        setStatus('ok');
        setMessage(reply.detail);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setStatus('bad');
        setMessage(err instanceof ApiError ? err.message : 'Invalid or expired link');
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="auth">
      <div className="auth-card">
        <h1>Email verification</h1>
        {status === 'pending' && <InfoText>Confirming your email…</InfoText>}
        {status === 'ok' && <InfoText>{message}</InfoText>}
        {status === 'bad' && <ErrorText>{message}</ErrorText>}
        <p className="mt-lg">
          <Link to="/login" className="text-neon-blue hover:text-neon-pink">
            Go to log in
          </Link>
        </p>
      </div>
    </main>
  );
}
