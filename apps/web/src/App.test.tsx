import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import App from './App';
import { AuthProvider } from './app/AuthContext';
import { ThemeProvider } from './app/theme';
import { ApiError, api } from './lib/api-client';

function renderApp(path = '/') {
  const user = userEvent.setup();
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
  return { user, ...view };
}

describe('App routing (WEB-004/005/006/008)', () => {
  it('shows the landing descent to unauthenticated visitors at /', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'CHESS NGINC' })).toBeInTheDocument();
    // the nav ticket box and the finale CTA both offer sign up
    expect((await screen.findAllByRole('link', { name: 'Sign up' })).length).toBeGreaterThan(1);
  });

  it('shows a session-restoration loading state before /auth/me resolves', () => {
    vi.spyOn(api, 'me').mockReturnValueOnce(new Promise(() => undefined));
    renderApp('/');
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('renders the dashboard when a session is restored', async () => {
    vi.spyOn(api, 'me').mockResolvedValueOnce({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'listGames').mockResolvedValueOnce([]);
    vi.spyOn(api, 'listAchievements').mockResolvedValueOnce({
      total: 2,
      unlocked: 0,
      items: [],
    });
    renderApp('/');
    expect(await screen.findByText('a@b.co')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Your Games' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Achievements' })).toBeInTheDocument();
  });

  it('returns to the landing descent after logging out', async () => {
    vi.spyOn(api, 'me').mockResolvedValueOnce({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'listGames').mockResolvedValueOnce([]);
    vi.spyOn(api, 'listAchievements').mockResolvedValueOnce({ total: 0, unlocked: 0, items: [] });
    const logout = vi.spyOn(api, 'logout').mockResolvedValue(undefined);
    const { user } = renderApp('/');

    await user.click(await screen.findByRole('button', { name: /a@b\.co/ }));
    await user.click(await screen.findByRole('menuitem', { name: 'Log out' }));

    expect(logout).toHaveBeenCalledTimes(1);
    // context user goes null; `/` re-renders as the landing for the visitor
    expect(await screen.findByRole('heading', { name: 'CHESS NGINC' })).toBeInTheDocument();
  });

  it('logs in from the login form and lands on the dashboard', async () => {
    const me = vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const login = vi
      .spyOn(api, 'login')
      .mockResolvedValueOnce({ id: 1, email: 'a@b.co', points: 0 });
    const list = vi.spyOn(api, 'listGames').mockResolvedValueOnce([]);
    vi.spyOn(api, 'listAchievements').mockResolvedValueOnce({ total: 0, unlocked: 0, items: [] });
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

  it('wires the Google sign-in slot into both auth forms', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const { user } = renderApp('/login');

    // Both cards carry the Google slot markup; with no client ID configured the
    // widget and its divider stay hidden on login and register alike.
    await screen.findByRole('heading', { name: 'Log in' });
    expect(document.querySelector('.auth-card .google-btn-wrap')).toBeNull();
    expect(document.querySelector('.auth-card .auth-divider')).toBeNull();

    await user.click(screen.getByRole('link', { name: 'Create an account' }));
    await screen.findByRole('heading', { name: 'Create Account' });
    expect(document.querySelector('.auth-card .google-btn-wrap')).toBeNull();
    expect(document.querySelector('.auth-card .auth-divider')).toBeNull();
  });

  it('navigates from the login page to the forgot-password flow', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const { user } = renderApp('/login');

    // No Google button without a configured client ID.
    expect(document.querySelector('.google-btn-wrap')).toBeNull();

    await user.click(await screen.findByRole('link', { name: 'Forgot password?' }));
    expect(await screen.findByRole('heading', { name: 'Forgot password' })).toBeInTheDocument();
  });

  it('requests a reset link and confirms without leaking account status', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const forgot = vi
      .spyOn(api, 'forgotPassword')
      .mockResolvedValueOnce({ message: 'If an account exists, a reset link is on its way.' });
    const { user } = renderApp('/forgot-password');

    await user.type(screen.getByLabelText('Email'), 'a@b.co');
    await user.click(screen.getByRole('button', { name: 'Send reset link' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Check your inbox');
    expect(forgot).toHaveBeenCalledWith({ email: 'a@b.co' });
  });

  it('rejects mismatched passwords before calling the API', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const reset = vi.spyOn(api, 'resetPassword');
    const { user } = renderApp('/reset-password?token=abc123def456ghi789');

    await user.type(screen.getByLabelText('New password'), 'brand-new-pass');
    await user.type(screen.getByLabelText('Confirm password'), 'different-pass');
    await user.click(screen.getByRole('button', { name: 'Set new password' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('do not match');
    expect(reset).not.toHaveBeenCalled();
  });

  it('completes the reset using the token from the link', async () => {
    vi.spyOn(api, 'me').mockRejectedValueOnce(new Error('nope'));
    const reset = vi.spyOn(api, 'resetPassword').mockResolvedValueOnce({ message: 'done' });
    const { user } = renderApp('/reset-password?token=abc123def456ghi789');

    await user.type(screen.getByLabelText('New password'), 'brand-new-pass');
    await user.type(screen.getByLabelText('Confirm password'), 'brand-new-pass');
    await user.click(screen.getByRole('button', { name: 'Set new password' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Password updated');
    expect(reset).toHaveBeenCalledWith({ token: 'abc123def456ghi789', password: 'brand-new-pass' });
  });

  it('lazy-loads a code-split page behind its Suspense boundary (RB-006)', async () => {
    vi.spyOn(api, 'me').mockResolvedValueOnce({ id: 1, email: 'a@b.co', points: 0 });
    vi.spyOn(api, 'trainingSummary').mockResolvedValue({
      puzzles_solved: 0,
      streak: 0,
      mine_available: 0,
      themes: {},
    } as never);
    vi.spyOn(api, 'trainingMine').mockResolvedValue([] as never);

    // /learn is no longer in the eager chunk (the build proves the split);
    // this asserts the lazily imported page still renders correctly through
    // its Suspense boundary (async queries get their headroom from setup.ts).
    renderApp('/learn');
    expect(await screen.findByRole('heading', { name: 'Learn the patterns' })).toBeInTheDocument();
  });
});
