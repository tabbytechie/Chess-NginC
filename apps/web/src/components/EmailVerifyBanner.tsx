/**
 * Unverified-email banner (SEC-013). Shown on protected pages while the signed-in
 * account's address is unconfirmed, with a resend control. Dismissible for the
 * session; resending is best-effort and always reports the same generic result so
 * the flow cannot enumerate accounts.
 */
import { useState } from 'react';

import { useAuth } from '../app/useAuth';
import { api } from '../lib/api-client';

export function EmailVerifyBanner() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!user || user.email_verified || dismissed) return null;

  const email = user.email;

  async function resend() {
    setBusy(true);
    try {
      await api.resendVerification({ email });
      setSent(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="verify-banner" role="status">
      <span>
        {sent
          ? 'Verification link re-sent. Check your inbox.'
          : 'Your email address is not verified yet. Verify it to secure account recovery.'}
      </span>
      <div className="verify-banner-actions">
        <button type="button" className="btn btn-small" onClick={resend} disabled={busy}>
          {busy ? 'Sending…' : 'Resend link'}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => setDismissed(true)}>
          Dismiss
        </button>
      </div>
    </div>
  );
}
