"""
Run the Django app against the dedicated performance database.

Rewrites DATABASE_URL to point at ``chatbot_perf`` (created by
``setup_perf_db.py``) without printing any credentials, then starts
uvicorn.

Usage:
    uv run python performance/run_server.py
    PERF_WORKERS=4 uv run python performance/run_server.py
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import environ

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "chatbot"))

env = environ.Env()
env.read_env(ROOT / ".env")

PERF_DB_NAME = os.environ.get("PERF_DB_NAME", "chatbot_perf")
# Supabase session-mode pooler (5432) caps clients at pool_size=15.
# Transaction-mode pooler (6543) multiplexes connections and is the
# supported mode for a multi-worker Django deployment.
PERF_DB_PORT = os.environ.get("PERF_DB_PORT", "6543")
parts = urlparse(env("DATABASE_URL"))
netloc = f"{parts.username}:{parts.password}@{parts.hostname}:{PERF_DB_PORT}"
os.environ["DATABASE_URL"] = urlunparse(
    parts._replace(path=f"/{PERF_DB_NAME}", netloc=netloc)
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# The Supabase transaction pooler caps client connections at 200.
# Closing DB connections at request end keeps concurrent connections
# proportional to in-flight requests instead of the thread-pool size.
os.environ.setdefault("DB_CONN_MAX_AGE", "0")

import uvicorn  # noqa: E402

if __name__ == "__main__":
    workers = int(os.environ.get("PERF_WORKERS", "2"))
    port = int(os.environ.get("PERF_PORT", "8000"))
    print(
        f"[server] uvicorn on http://127.0.0.1:{port} "
        f"db={PERF_DB_NAME} workers={workers}",
        flush=True,
    )
    uvicorn.run(
        "config.asgi:application",
        host="127.0.0.1",
        port=port,
        workers=workers,
    )
