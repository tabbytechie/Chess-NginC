import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import App from './App';
import { AuthProvider } from './app/AuthContext';
import { ApiError, api } from './lib/api-client';
import type { GameListResponse, StatsResponse, UserResponse } from './lib/api-types';

const EMPTY_LIST: GameListResponse = { items: [], total: 0, limit: 20, offset: 0 };
const EMPTY_STATS: StatsResponse = { by_mode: {} };
const USER: UserResponse = { id: 1, email: 'a@b.co', email_verified: true };

function renderApp(path = '/') {
  const user = userEvent.setup();
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return { user, ...view };
}

describe('App routing (WEB-004/005/006/008)', () => {
  it('redirects unauthenticated users from / to the login page', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  });

  it('shows a session-restoration loading state before /auth/me resolves', () => {
    vi.spyOn(api, 'me').mockReturnValueOnce(new Promise(() => undefined));
    renderApp('/');
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('renders the dashboard when a session is restored', async () => {
    vi.spyOn(api, 'me').mockResolvedValueOnce({ ...USER });
    vi.spyOn(api, 'listGames').mockResolvedValueOnce(EMPTY_LIST);
    vi.spyOn(api, 'stats').mockResolvedValueOnce(EMPTY_STATS);
    renderApp('/');
    expect(await screen.findByText('a@b.co')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Your Games' })).toBeInTheDocument();
  });

  it('logs in from the login form and lands on the dashboard', async () => {
    const me = vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const login = vi.spyOn(api, 'login').mockResolvedValueOnce({ ...USER });
    const list = vi.spyOn(api, 'listGames').mockResolvedValueOnce(EMPTY_LIST);
    vi.spyOn(api, 'stats').mockResolvedValueOnce(EMPTY_STATS);
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'supersecret1');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    // Wait for the Dashboard itself (not the TopNav email, which renders
    // before navigate('/') mounts the Dashboard and fires listGames).
    expect(await screen.findByRole('heading', { name: 'Your Games' })).toBeInTheDocument();
    expect(screen.getByText('a@b.co')).toBeInTheDocument();
    expect(login).toHaveBeenCalledWith({ email: 'a@b.co', password: 'supersecret1' });
    expect(me).toHaveBeenCalled();
    expect(list).toHaveBeenCalled();
  });

  it('rejects a short password before calling the API (WEB-025)', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const login = vi.spyOn(api, 'login');
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters');
    expect(login).not.toHaveBeenCalled();
  });

  it('surfaces server errors as an alert', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    vi.spyOn(api, 'login').mockRejectedValueOnce(new ApiError(401, 'Invalid email or password'));
    const { user } = renderApp('/login');

    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.type(screen.getByLabelText('Password'), 'supersecret1');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password');
  });

  it('renders the forgot-password page as a public route', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    renderApp('/forgot-password');
    expect(await screen.findByRole('heading', { name: 'Forgot password' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
  });

  it('requests a reset link and shows the generic confirmation', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const req = vi
      .spyOn(api, 'requestPasswordReset')
      .mockResolvedValueOnce({ detail: 'If that email is registered, a link has been sent.' });
    const { user } = renderApp('/forgot-password');
    await user.type(await screen.findByLabelText('Email'), 'a@b.co');
    await user.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByRole('status')).toHaveTextContent('reset link is on its way');
    expect(req).toHaveBeenCalledWith({ email: 'a@b.co' });
  });

  it('shows the unverified banner for an account awaiting verification', async () => {
    vi.spyOn(api, 'me').mockResolvedValueOnce({ ...USER, email_verified: false });
    vi.spyOn(api, 'listGames').mockResolvedValueOnce(EMPTY_LIST);
    vi.spyOn(api, 'stats').mockResolvedValueOnce(EMPTY_STATS);
    const resend = vi
      .spyOn(api, 'resendVerification')
      .mockResolvedValueOnce({ detail: 'If that email is registered, a link has been sent.' });
    const { user } = renderApp('/');
    expect(await screen.findByText(/not verified/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Resend link' }));
    expect(resend).toHaveBeenCalledWith({ email: 'a@b.co' });
  });

  it('hides the unverified banner once the email is confirmed', async () => {
    vi.spyOn(api, 'me').mockResolvedValueOnce({ ...USER, email_verified: true });
    vi.spyOn(api, 'listGames').mockResolvedValueOnce(EMPTY_LIST);
    vi.spyOn(api, 'stats').mockResolvedValueOnce(EMPTY_STATS);
    renderApp('/');
    await screen.findByRole('heading', { name: 'Your Games' });
    expect(screen.queryByText(/not verified/)).not.toBeInTheDocument();
  });
});
