#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
python3 scripts/bitpolito/brand.py check
(cd apps/deckcraft-web && trunk build --release --locked=true)
python3 scripts/bitpolito/build-info.py
