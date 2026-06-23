#!/usr/bin/env bash
# Prebuild всех default_packs из config/city_packs.yaml
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
for slug in $("$PYTHON" -c 'from config.city_catalog import default_pack_slugs; print(" ".join(default_pack_slugs()))'); do
  echo "========== $slug =========="
  bash "$ROOT/scripts/city_pack_prepare.sh" "$slug"
done
