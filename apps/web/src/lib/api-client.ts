/**
 * Typed API client (WEB-025: explicit loading/error states via ApiError).
 * All requests send same-origin cookies; base URL is configurable for prod.
 */
import type {
  CreateGameRequest,
  EmailRequest,
  EngineMoveRequest,
  ErrorResponse,
  GameListResponse,
  GameResponse,
  LoginRequest,
  MoveRequest,
  RecoveryMessage,
  RegisterRequest,
  ResetPasswordRequest,
  StatsResponse,
  UserResponse,
  VerifyEmailRequest,
  VersionRequest,
} from './api-types';

export const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/api/v1${path}`, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch (err) {
    throw new ApiError(0, err instanceof Error ? err.message : 'Network error');
  }
  if (resp.status === 204) return undefined as T;
  let body: unknown;
  try {
    body = await resp.json();
  } catch {
    body = null;
  }
  if (!resp.ok) {
    const detail = (body as ErrorResponse | null)?.detail ?? `Request failed (${resp.status})`;
    throw new ApiError(resp.status, detail);
  }
  return body as T;
}

const post = <T>(path: string, payload?: unknown): Promise<T> =>
  request<T>(path, { method: 'POST', body: JSON.stringify(payload ?? {}) });

const get = <T>(path: string): Promise<T> => request<T>(path);

export const api = {
  register: (p: RegisterRequest) => post<UserResponse>('/auth/register', p),
  login: (p: LoginRequest) => post<UserResponse>('/auth/login', p),
  logout: () => post<void>('/auth/logout'),
  me: () => get<UserResponse>('/auth/me'),

  createGame: (p: CreateGameRequest) => post<GameResponse>('/games', p),
  listGames: (params: { status?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.limit != null) query.set('limit', String(params.limit));
    if (params.offset != null) query.set('offset', String(params.offset));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return get<GameListResponse>(`/games${suffix}`);
  },
  stats: () => get<StatsResponse>('/stats'),
  getGame: (id: number) => get<GameResponse>(`/games/${id}`),
  submitMove: (id: number, p: MoveRequest) => post<GameResponse>(`/games/${id}/moves`, p),
  undoMove: (id: number, p: VersionRequest) => post<GameResponse>(`/games/${id}/undo`, p),
  resignGame: (id: number) => post<GameResponse>(`/games/${id}/resign`),
  claimDraw: (id: number) => post<GameResponse>(`/games/${id}/draw-claim`),
  engineMove: (id: number, p: EngineMoveRequest) =>
    post<GameResponse>(`/games/${id}/engine-move`, p),

  // Account recovery (SEC-013). Each returns the same uniform reply shape so
  // the caller can never learn whether an email is registered.
  verifyEmail: (p: VerifyEmailRequest) => post<RecoveryMessage>('/auth/verify-email', p),
  resendVerification: (p: EmailRequest) => post<RecoveryMessage>('/auth/resend-verification', p),
  requestPasswordReset: (p: EmailRequest) =>
    post<RecoveryMessage>('/auth/request-password-reset', p),
  resetPassword: (p: ResetPasswordRequest) => post<RecoveryMessage>('/auth/reset-password', p),
};

/** Absolute URL for the PGN download; the browser saves it as an attachment. */
export function pgnDownloadUrl(id: number): string {
  return `${API_BASE}/api/v1/games/${id}/pgn`;
}
