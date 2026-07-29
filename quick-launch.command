#!/usr/bin/env bash

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec /bin/bash "$SCRIPT_DIR/quick-launch.sh"
