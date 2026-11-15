import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional in production
    pass


# --- App metadata -------------------------------------------------------

APP_NAME = "RexWork"
APP_VERSION = "1.1.0"

# Optional shared secret. When set, CLI/non-browser callers can pass it in
# `X-App-Token`. Logged-in browser users authenticate via Supabase Bearer JWT.
APP_TOKEN = (os.getenv("APP_TOKEN") or "").strip()

# Supabase project used to verify logged-in user Bearer tokens. Falls back to
# the project's public URL & publishable key when env vars are not set on Vercel.
DEFAULT_SUPABASE_URL = "https://fdlklzveockeibcmijmz.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_fhqAyClsPwkXDrqQVD2H5g_L1zyGihq"

SUPABASE_URL = (os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL).strip().rstrip("/")
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_PUBLISHABLE_KEY")
    or (DEFAULT_SUPABASE_KEY if SUPABASE_URL == DEFAULT_SUPABASE_URL else "")
).strip()

# API routes that are allowed to answer without authentication. They only
# expose static/health information, never model access.
OPEN_PATHS = {
    "/api/status",
    "/api/index",
    "/api/index.py",
    "/api/health",
}


# endpoints for provider :>
GROQ_BASE_URL = (
    os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
).rstrip("/")
GROQ_CHAT_URL = f"{GROQ_BASE_URL}/chat/completions"
GROQ_TRANSCRIBE_URL = f"{GROQ_BASE_URL}/audio/transcriptions"
GROQ_TRANSCRIBE_MODEL = os.getenv("GROQ_TRANSCRIBE_MODEL") or "whisper-large-v3"


MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TEXT_CHARS = 20000
MAX_MESSAGES = 100
MAX_MESSAGE_CHARS = 50000
MAX_CANVAS_CHARS = 30000
MAX_MEMORY_ITEMS = 50
MAX_TRANSCRIPTION_BYTES = 25 * 1024 * 1024
MAX_TOKENS_CAP = 8192
MAX_CONTENT_PARTS = 50

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048


REASONING_MODEL_PREFIXES = ("openai/gpt-oss",)
RETRY_REASONING_EFFORT = "low"

KEY_COOLDOWN_SECONDS = 60
MAX_API_KEYS = 20

# frontends location
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.normpath(os.path.join(BACKEND_DIR, "..", "Frontend"))
INDEX_FILE = os.path.join(FRONTEND_DIR, "index.html")
LOGIN_FILE = os.path.join(FRONTEND_DIR, "Main.html")
