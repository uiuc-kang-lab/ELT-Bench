#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible Snowflake shortcut. New runs should call run_elt.py
# directly and select any supported destination with --destination.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python "$SCRIPT_DIR/run_elt.py" --destination snowflake "$@"
