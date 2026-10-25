/**
 * Typed API client (WEB-025: explicit loading/error states via ApiError).
 * All requests send same-origin cookies; base URL is configurable for prod.
 */
import type {
  AchievementListResponse,
  AchievementResponse,
  AssistantAnswerResponse,
  AssistantAskRequest,
  CoachPatternsResponse,
  CreateGameRequest,
  EngineMoveRequest,
  ErrorResponse,
  ForgotPasswordRequest,
  GameResponse,
  GoogleLoginRequest,
  LoginRequest,
  MessageResponse,
  MinePuzzleResponse,
  MoveRequest,
  PuzzleResponse,
  QueueResponse,
  RegisterRequest,
  ResetPasswordRequest,
  ReviewRequest,
  ReviewResponse,
  TrainingAttemptRequest,
  TrainingAttemptResponse,
  TrainingSummaryResponse,
  UserResponse,
  VersionRequest,
  VoiceListResponse,
  VoicePreferences,
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

const put = <T>(path: string, payload?: unknown): Promise<T> =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(payload ?? {}) });

const del = <T>(path: string): Promise<T> => request<T>(path, { method: 'DELETE' });

export const api = {
  register: (p: RegisterRequest) => post<UserResponse>('/auth/register', p),
  login: (p: LoginRequest) => post<UserResponse>('/auth/login', p),
  logout: () => post<void>('/auth/logout'),
  me: () => get<UserResponse>('/auth/me'),
  forgotPassword: (p: ForgotPasswordRequest) => post<MessageResponse>('/auth/forgot-password', p),
  resetPassword: (p: ResetPasswordRequest) => post<MessageResponse>('/auth/reset-password', p),
  googleLogin: (p: GoogleLoginRequest) => post<UserResponse>('/auth/google', p),

  createGame: (p: CreateGameRequest) => post<GameResponse>('/games', p),
  listGames: () => get<GameResponse[]>('/games'),
  getGame: (id: number) => get<GameResponse>(`/games/${id}`),
  submitMove: (id: number, p: MoveRequest) => post<GameResponse>(`/games/${id}/moves`, p),
  undoMove: (id: number, p: VersionRequest) => post<GameResponse>(`/games/${id}/undo`, p),
  resignGame: (id: number) => post<GameResponse>(`/games/${id}/resign`),
  claimDraw: (id: number) => post<GameResponse>(`/games/${id}/draw-claim`),
  engineMove: (id: number, p: EngineMoveRequest) =>
    post<GameResponse>(`/games/${id}/engine-move`, p),

  // Post-game engine review (REVIEW-001/005).
  createGameReview: (id: number, p: ReviewRequest = {}) =>
    post<ReviewResponse>(`/games/${id}/review`, p),
  getGameReview: (id: number) => get<ReviewResponse>(`/games/${id}/review`),

  // Coach assistant (Phase 11): a grounded question over the reviewed game,
  // plus cross-game pattern recall. Both are read-only from the DB's view.
  askCoach: (id: number, p: AssistantAskRequest) =>
    post<AssistantAnswerResponse>(`/games/${id}/assistant`, p),
  coachPatterns: (id: number) => get<CoachPatternsResponse>(`/games/${id}/assistant/patterns`),

  // Online play (online-plan §6): lobby queue + participant-scoped game routes.
  joinQueue: () => post<QueueResponse>('/online/queue'),
  leaveQueue: () => del<void>('/online/queue'),
  queueStatus: () => get<QueueResponse>('/online/queue'),
  listOnlineGames: () => get<GameResponse[]>('/online/games'),
  getOnlineGame: (id: number) => get<GameResponse>(`/online/games/${id}`),
  submitOnlineMove: (id: number, p: MoveRequest) =>
    post<GameResponse>(`/online/games/${id}/moves`, p),
  resignOnlineGame: (id: number) => post<GameResponse>(`/online/games/${id}/resign`),
  claimOnlineDraw: (id: number) => post<GameResponse>(`/online/games/${id}/draw-claim`),

  // Achievements (ACH-005..007): gallery, lazy catch-up, acknowledgement.
  listAchievements: () => get<AchievementListResponse>('/me/achievements'),
  newAchievements: () => get<AchievementResponse[]>('/me/achievements/new'),
  markAchievementsSeen: (keys: string[]) =>
    post<MessageResponse>('/me/achievements/seen', { keys }),

  // Training / Learn (LEARN-002/003/004/005): progress, puzzles, own-game drills.
  trainingSummary: () => get<TrainingSummaryResponse>('/training/summary'),
  trainingPuzzle: (theme?: string, source?: string) => {
    const params = new URLSearchParams();
    if (theme) params.set('theme', theme);
    if (source) params.set('source', source);
    const query = params.toString();
    return get<PuzzleResponse>(`/training/puzzle${query ? `?${query}` : ''}`);
  },
  trainingMine: () => get<MinePuzzleResponse[]>('/training/mine'),
  submitTrainingAttempt: (p: TrainingAttemptRequest) =>
    post<TrainingAttemptResponse>('/training/attempts', p),

  // Voice (REVIEW-009 + Phase 12 AI-coach narration): the free premium-voice
  // catalog and the caller's server-side consent + selected voice.
  listVoices: () => get<VoiceListResponse>('/tts/voices'),
  getVoicePrefs: () => get<VoicePreferences>('/me/voice'),
  saveVoicePrefs: (p: Partial<VoicePreferences>) => put<VoicePreferences>('/me/voice', p),
};
