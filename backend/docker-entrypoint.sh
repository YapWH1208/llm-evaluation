#!/usr/bin/env bash
set -euo pipefail

: "${LLE_DATA_ROOT:=/data}"

if [[ -z "${LLE_SECRET_ENCRYPTION_KEY:-}" ]]; then
    SECRET_FILE="$LLE_DATA_ROOT/.lle-secret-key"
    mkdir -p "$LLE_DATA_ROOT"
    LLE_SECRET_ENCRYPTION_KEY="$(python3 - "$SECRET_FILE" <<'PY'
import os, stat, sys
from pathlib import Path
from cryptography.fernet import Fernet

path = Path(sys.argv[1])
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    mode = stat.S_IMODE(os.lstat(path).st_mode)
    if not path.is_file() or path.is_symlink() or mode != 0o600:
        raise SystemExit("Refusing insecure LLE secret file; expected a regular file with mode 0600.")
    print(path.read_text().strip(), end="")
else:
    key = Fernet.generate_key().decode()
    try:
        os.write(fd, key.encode())
    finally:
        os.close(fd)
    print(key, end="")
PY
)"
    export LLE_SECRET_ENCRYPTION_KEY
fi

exec "$@"
