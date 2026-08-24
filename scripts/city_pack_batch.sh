#!/usr/bin/env bash
# Prebuild extract+poi для каталога (hot+warm по умолчанию).
#   bash scripts/city_pack_batch.sh
#   bash scripts/city_pack_batch.sh --tier=hot
#   bash scripts/city_pack_batch.sh --tier=warm
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

TIER=""
if [[ "${1:-}" == --tier=* ]]; then
  TIER="${1#--tier=}"
elif [[ "${1:-}" == "--tier" && -n "${2:-}" ]]; then
  TIER="$2"
fi

SLUGS="$("$PYTHON" - "$TIER" <<'PY'
import sys
from config.city_catalog import catalog_slugs
tier = (sys.argv[1] or "").strip() or None
print(" ".join(catalog_slugs(tier=tier)))
PY
)"

if [[ -z "${SLUGS// }" ]]; then
  echo "Нет slug для prepare" >&2
  exit 1
fi

for slug in $SLUGS; do
  echo "========== $slug =========="
  bash "$ROOT/scripts/city_pack_prepare.sh" "$slug"
done
