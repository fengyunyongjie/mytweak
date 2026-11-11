#!/bin/bash
# Build only into a new .build/examples tree; never install or publish packages.
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -I "$SCRIPT_DIR/../scripts/build_example.py" "$@"
