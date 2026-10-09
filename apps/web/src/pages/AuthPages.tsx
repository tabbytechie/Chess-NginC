/** Registration + login forms (WEB-005/006/025). */
import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../app/useAuth';

function useAuthForm(submit: (email: string, password: string) => Promise<void>) {
  const navigate = useNavigate();
  const location = useLocation();
  const { error, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    clearError();
    setLocalError(null);
    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters.');
      return;
    }
    setBusy(true);
    try {
      await submit(email.trim(), password);
      const from = (location.state as { from?: string } | null)?.from ?? '/';
      navigate(from, { replace: true });
    } catch {
      // Error surfaces via context; keep form state for retry.
    } finally {
      setBusy(false);
    }
  }
  return { email, setEmail, password, setPassword, busy, error: localError ?? error, onSubmit };
}

export function RegisterPage() {
  const { register } = useAuth();
  const form = useAuthForm(register);
  return (
    <main className="auth">
      <div className="auth-card">
        <h1>Create account</h1>
        <form onSubmit={form.onSubmit} aria-label="registration form">
          <label htmlFor="register-email">Email</label>
          <input
            id="register-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={(e) => form.setEmail(e.target.value)}
          />
          <label htmlFor="register-password">Password (min 8 characters)</label>
          <input
            id="register-password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            value={form.password}
            onChange={(e) => form.setPassword(e.target.value)}
          />
          {form.error && (
            <p role="alert" className="error">
              {form.error}
            </p>
          )}
          <button type="submit" disabled={form.busy}>
            {form.busy ? 'Creating…' : 'Create account'}
          </button>
        </form>
        <p>
          Have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </main>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const form = useAuthForm(login);
  return (
    <main className="auth">
      <div className="auth-card">
        <h1>Log in</h1>
        <form onSubmit={form.onSubmit} aria-label="login form">
          <label htmlFor="login-email">Email</label>
          <input
            id="login-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={(e) => form.setEmail(e.target.value)}
          />
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={form.password}
            onChange={(e) => form.setPassword(e.target.value)}
          />
          {form.error && (
            <p role="alert" className="error">
              {form.error}
            </p>
          )}
          <button type="submit" disabled={form.busy}>
            {form.busy ? 'Logging in…' : 'Log in'}
          </button>
        </form>
        <p>
          New here? <Link to="/register">Create an account</Link>
        </p>
      </div>
    </main>
  );
}
