"""Central configuration for the HERMUS Cloud + Local Core API."""
import os

# DB connection. In hosted deployments (Render/Heroku/etc.) a single DATABASE_URL
# is provided — prefer it. Otherwise fall back to the per-part HERMUS_DB_* vars
# used by local dev and the desktop app.
DB_SSL = False
_raw = os.getenv("DATABASE_URL", "").strip()

if _raw:
    # Strip the ?sslmode=... query (pg8000 doesn't understand it) and decide SSL
    # ourselves. Render's *internal* URL needs no SSL; the *external* one does.
    base, _, query = _raw.partition("?")
    if ("sslmode=require" in query) or (".render.com" in base) or (os.getenv("HERMUS_DB_SSL") == "1"):
        DB_SSL = True
    # Normalise the scheme to the pg8000 driver SQLAlchemy expects.
    if base.startswith("postgres://"):
        base = "postgresql+pg8000://" + base[len("postgres://"):]
    elif base.startswith("postgresql://") and "+pg8000" not in base:
        base = "postgresql+pg8000://" + base[len("postgresql://"):]
    DATABASE_URL = base
else:
    DB_HOST = os.getenv("HERMUS_DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("HERMUS_DB_PORT", "5544")
    DB_USER = os.getenv("HERMUS_DB_USER", "hermus")
    DB_NAME = os.getenv("HERMUS_DB_NAME", "hermus")
    DB_PASS = os.getenv("HERMUS_DB_PASS", "")
    if DB_PASS:
        DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        DATABASE_URL = f"postgresql+pg8000://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

JWT_SECRET = os.getenv("HERMUS_JWT_SECRET", "hermus-dev-secret-change-me")
JWT_ALG = "HS256"
JWT_TTL_MIN = int(os.getenv("HERMUS_JWT_TTL_MIN", "720"))

# Default approval thresholds (Conditional Document §11, configurable per agent).
THRESHOLDS = {
    "specialist_limit": 5000,   # AC-01
    "manager_limit": 25000,     # AC-02
    "ceo_limit": 50000,         # AC-03 -> above this = human (AC-04)
    "bulk_records": 50,         # AC-06
    "approval_timeout_hours": 4,  # AC-08
    "stt_auto_confidence": 0.85,  # VC-01
}

CORS_ORIGINS = os.getenv(
    "HERMUS_CORS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
).split(",")
