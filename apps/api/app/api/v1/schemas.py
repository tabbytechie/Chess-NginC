"""HTTP request/response schemas for API v1 (SEC-016: safe error shapes)."""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """Registration payload."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=256)


class LoginRequest(BaseModel):
    """Login payload."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    """Password-reset request (email only)."""

    email: str = Field(max_length=255)


class ResetPasswordRequest(BaseModel):
    """Password-reset completion payload."""

    token: str = Field(min_length=16, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class GoogleLoginRequest(BaseModel):
    """Google Sign-In payload: the ID token from Google Identity Services."""

    credential: str = Field(min_length=16, max_length=8192)


class MessageResponse(BaseModel):
    """Neutral operational message (never leaks account existence)."""

    message: str


class UserResponse(BaseModel):
    """Public user representation (never includes password hash)."""

    id: int
    email: str
    points: int


class ErrorResponse(BaseModel):
    """Consistent error envelope (SEC-016)."""

    detail: str


class CreateGameRequest(BaseModel):
    """Game creation payload (API-005)."""

    mode: str = Field(default="local", max_length=50)


class MoveRequest(BaseModel):
    """Move submission payload (API-008/019)."""

    uci: str = Field(min_length=4, max_length=10)
    expected_version: int = Field(ge=1)


class VersionRequest(BaseModel):
    """Payload for version-guarded actions (API-009/012)."""

    expected_version: int = Field(ge=1)


class EngineMoveRequest(BaseModel):
    """Engine move payload with optional search budget (API-012)."""

    expected_version: int = Field(ge=1)
    max_depth: int | None = Field(default=None, ge=1, le=6)
    max_time_ms: int | None = Field(default=None, ge=100, le=3000)


class MoveResponse(BaseModel):
    """A stored move."""

    uci: str
    san: str
    move_number: int


class AchievementResponse(BaseModel):
    """One catalog entry (ACH-005)."""

    key: str
    title: str
    description: str
    metric: str
    threshold: int
    tier: str  # bronze|silver|gold|diamond|legendary
    group: str  # play|result|points|tactics|pieces|endurance|habit|review|engine|mode|training


class GameResponse(BaseModel):
    """A game with its move history (API-006/007)."""

    id: int
    mode: str
    status: str
    fen: str
    version: int
    moves: list[MoveResponse] = Field(default_factory=list)
    # Online games only: the color seats. The frontend derives "am I White?"
    # from white_user_id === me.id, never a per-request echoed flag (§8).
    white_user_id: int | None = None
    black_user_id: int | None = None
    # Achievements unlocked by this action (ACH-006); empty for reads.
    unlocked_achievements: list[AchievementResponse] = Field(default_factory=list)


class AchievementProgressResponse(AchievementResponse):
    """A catalog entry as seen by one player: progress plus unlock state."""

    value: int = 0
    unlocked: bool = False
    progress: float = 0.0  # 0..1 toward the threshold
    unlocked_at: str | None = None


class AchievementListResponse(BaseModel):
    """The gallery payload: whole catalog with per-player progress."""

    total: int
    unlocked: int
    items: list[AchievementProgressResponse] = Field(default_factory=list)


class AchievementSeenRequest(BaseModel):
    """Celebration acknowledgement (ACH-007): stop replaying these toasts."""

    keys: list[str] = Field(default_factory=list)


class QueueResponse(BaseModel):
    """Lobby queue state (online-plan §5)."""

    status: str  # 'idle' | 'queued' | 'matched'
    game_id: int | None = None
    color: str | None = None  # 'w' | 'b' when matched


class ReviewRequest(BaseModel):
    """Review generation payload (REVIEW-001)."""

    force: bool = False  # re-analyze even when a stored review exists


class ReviewMoveResponse(BaseModel):
    """One classified ply with its engine facts and coaching line."""

    ply: int
    move_number: int
    uci: str
    san: str
    # Position the move was played from, so the page can render a board per ply.
    pre_fen: str = ""
    color: str  # 'w' | 'b'
    quality: str  # brilliant|best|excellent|good|inaccuracy|mistake|blunder
    centipawn_loss: int
    best_uci: str = ""
    eval_cp: int = 0  # after the ply, from the MOVER's perspective
    eval_mate: int | None = None
    explanation: str = ""
    # Derived on read, never stored: `app/reviews/annotate.py` resolves these
    # from the theory book and the eval above (REVIEW-008 / ANL-004 / COA-004).
    # Optional so reviews stored before they existed still validate.
    opening_eco: str | None = None
    opening_name: str | None = None
    in_book: bool = False
    # White's perspective, 1..99; flip it for a hero playing Black.
    win_pct: int | None = None


class ReviewEvalPoint(BaseModel):
    """One point of the evaluation graph (white's perspective)."""

    ply: int
    cp: int
    mate: int | None = None


class ReviewImprovement(BaseModel):
    """A mistake/blunder the player could have played better."""

    ply: int
    san: str
    color: str
    best_uci: str
    loss_cp: int


class ReviewSummary(BaseModel):
    """Aggregate accuracy per side (0..100) plus ply count."""

    ply_count: int = 0
    accuracy: dict[str, int] = Field(default_factory=dict)


class ReviewResponse(BaseModel):
    """A stored game review, served without re-analysis (REVIEW-005)."""

    id: int
    game_id: int
    status: str  # 'completed' | 'failed'
    provider: str
    depth: int
    hero_color: str
    error: str | None = None
    summary: ReviewSummary = Field(default_factory=ReviewSummary)
    counts: dict[str, int] = Field(default_factory=dict)
    moves: list[ReviewMoveResponse] = Field(default_factory=list)
    eval_graph: list[ReviewEvalPoint] = Field(default_factory=list)
    improvements: list[ReviewImprovement] = Field(default_factory=list)
    # A completed review is itself an achievement milestone (ACH-006).
    unlocked_achievements: list[AchievementResponse] = Field(default_factory=list)


class TrainingThemeProgress(BaseModel):
    """One skill card's numbers (LEARN-003)."""

    label: str
    solved: int
    attempts: int
    level: int  # 1..3 ramp rung to offer next
    pct: float  # 0..1 completion of the theme's drills


class TrainingSummaryResponse(BaseModel):
    """The Learn page header: per-theme progress plus headline totals."""

    themes: dict[str, TrainingThemeProgress] = Field(default_factory=dict)
    puzzles_solved: int = 0
    streak: int = 0
    mine_available: int = 0


class PuzzleResponse(BaseModel):
    """A puzzle to attempt. Deliberately answer-free (never solution/line)."""

    key: str
    theme: str
    name: str
    level: int
    fen: str
    prompt: str
    source: str  # 'drill' | 'game'
    game_id: int | None = None  # set for mined puzzles, to link back to the review
    ply: int | None = None
    player_moves: int = 1  # how many own moves to play; >1 marks a multi-move puzzle


class TrainingAttemptRequest(BaseModel):
    """Submit a move, or ask to be shown the answer (LEARN-002)."""

    key: str = Field(min_length=1, max_length=64)
    uci: str = Field(default="", min_length=0, max_length=10)
    reveal: bool = False  # "Show me": records a no-credit attempt, gives the answer
    # Cumulative own-moves played so far, for multi-move puzzles; empty for singles.
    moves: list[str] = Field(default_factory=list, max_length=16)


class TrainingAttemptResponse(BaseModel):
    """The verdict and the reveal — the answer only ever leaves the server here."""

    solved: bool
    solution_san: str
    solution_from: str
    solution_to: str
    why: str
    continuation: list[str] = Field(default_factory=list)
    points_awarded: int = 0
    unlocked_achievements: list[AchievementResponse] = Field(default_factory=list)
    # Multi-move stepper fields; a single-move verdict is always terminal.
    complete: bool = True
    position_fen: str = ""
    played_san: list[str] = Field(default_factory=list)


class MinePuzzleResponse(BaseModel):
    """One mined puzzle in the 'from your own games' list (no answer)."""

    key: str
    fen: str
    prompt: str
    game_id: int
    ply: int


class CoachHistoryTurn(BaseModel):
    """One earlier turn of the thread, so follow-ups resolve against context."""

    role: str = Field(pattern=r"^(user|coach)$")
    text: str = Field(min_length=1, max_length=1000)


class AssistantAskRequest(BaseModel):
    """A coach question about the reviewed game (Phase 11).

    `focus_ply` is the ply the review cursor sits on; when it is None the
    assistant resolves the focus from the question text or the player's worst
    own error, so a bare question still lands somewhere useful. `history` is the
    recent thread (oldest first) so "and after that?" carries the last move.
    """

    question: str = Field(min_length=1, max_length=400)
    focus_ply: int | None = Field(default=None, ge=1, le=100000)
    history: list[CoachHistoryTurn] = Field(default_factory=list)


class AssistantReference(BaseModel):
    """One move the answer is grounded in — always a real, cited ply."""

    ply: int
    san: str
    color: str
    note: str = ""
    game_id: int | None = None


class AssistantLineStep(BaseModel):
    """One move of a walkable variation, with the board before and after it."""

    san: str
    uci: str
    color: str
    fen_before: str
    fen_after: str
    comment: str = ""
    source: str = "played"  # 'played' (recorded ply) | 'engine' (live PV)
    ply: int | None = None


class AssistantAnswerResponse(BaseModel):
    """The coach's grounded answer, its intent, the moves it cites, and a board line."""

    answer: str
    intent: str  # one of the Intent values in app.ai.compose
    mode: str  # 'deterministic' (always) | 'llm' (only when it stayed grounded)
    provider: str
    references: list[AssistantReference] = Field(default_factory=list)
    position_fen: str = ""
    line: list[AssistantLineStep] = Field(default_factory=list)
    line_title: str = ""


class CoachPattern(BaseModel):
    """One opening family's error tally across the player's reviewed games."""

    opening_family: str
    mistakes: int
    blunders: int
    total_errors: int
    avg_loss_cp: int


class CoachPatternsResponse(BaseModel):
    """The cross-game recall answer: a summary plus the counts it came from."""

    summary: str = ""
    items: list[CoachPattern] = Field(default_factory=list)


class VoiceOption(BaseModel):
    """One selectable narration voice.

    `engine` says how it is produced: `eleven` (server proxy, needs a key with
    the text_to_speech permission) or `browser` (the OS speech engine, always
    free/offline). `id` is the ElevenLabs voice id for `eleven`, or the browser
    voice name for `browser`. `available` is False for premium voices when no
    working key is configured, so the UI can grey them out honestly.
    """

    id: str
    name: str
    engine: str
    available: bool = True


class VoiceListResponse(BaseModel):
    """The curated free-tier ElevenLabs voices the server will proxy to."""

    voices: list[VoiceOption] = Field(default_factory=list)


class VoicePreferencesResponse(BaseModel):
    """The caller's stored voice choice + whether the AI is authorized to speak."""

    voice_authorized: bool
    voice_id: str


class VoicePreferencesUpdate(BaseModel):
    """Partial update: change consent, the voice, or both.

    `voice_id` is a short preference string (empty = browser default, an
    allowlisted id = an ElevenLabs voice, anything else = an OS voice name). The
    provider call at `POST /tts` is what enforces the allowlist; storing a name
    here is harmless and never reaches ElevenLabs.
    """

    voice_authorized: bool | None = None
    voice_id: str | None = Field(default=None, max_length=64)
