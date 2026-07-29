#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT_DIR"

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "Python 3 was not found on PATH." >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "npm was not found on PATH." >&2
    exit 1
fi

if ! "$PYTHON" -c "import cryptography, fastapi, uvicorn" >/dev/null 2>&1; then
    echo "Installing Python dependencies..."
    "$PYTHON" -m pip install -e '.[dev]'
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
    echo "Installing frontend dependencies..."
    npm --prefix "$ROOT_DIR/frontend" install
fi

if [[ -z "${LLE_SECRET_ENCRYPTION_KEY:-}" ]]; then
    SECRET_FILE="$ROOT_DIR/data/.lle-secret-key"
    export LLE_SECRET_FILE="$SECRET_FILE"
    "$PYTHON" -c 'import os, stat; from pathlib import Path; from cryptography.fernet import Fernet; path = Path(os.environ["LLE_SECRET_FILE"]); path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    mode = stat.S_IMODE(os.lstat(path).st_mode)
    if not path.is_file() or path.is_symlink() or mode != 0o600: raise SystemExit("Refusing insecure LLE secret file; expected a regular file with mode 0600.")
else:
    try: os.write(fd, Fernet.generate_key())
    finally: os.close(fd)
    os.chmod(path, 0o600)'
    export LLE_SECRET_ENCRYPTION_KEY="$(tr -d '[:space:]' < "$SECRET_FILE")"
fi

if [[ -z "$LLE_SECRET_ENCRYPTION_KEY" ]]; then
    echo "LLE_SECRET_ENCRYPTION_KEY is empty." >&2
    exit 1
fi

if [[ -z "${LLE_ADMIN_TOKEN:-}" && -z "${LLE_ALLOW_INSECURE_LOCAL_AUTH:-}" ]]; then
    export LLE_ALLOW_INSECURE_LOCAL_AUTH=true
fi

if [[ "${1:-}" == "--check" ]]; then
    echo "Quick launch checks passed."
    exit 0
fi

cleanup() {
    status=$?
    trap - EXIT INT TERM
    kill "$API_PID" "$WEB_PID" 2>/dev/null || true
    wait "$API_PID" "$WEB_PID" 2>/dev/null || true
    exit "$status"
}

echo "Starting the API at http://127.0.0.1:8000"
"$PYTHON" -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000 &
API_PID=$!

echo "Starting the web app at http://127.0.0.1:5173"
(
    cd "$ROOT_DIR/frontend"
    exec npm run dev -- --host 127.0.0.1
) &
WEB_PID=$!

trap cleanup EXIT INT TERM
echo "Both services are running. Open http://127.0.0.1:5173 in your browser."
echo "Press Ctrl+C to stop both services."
wait
