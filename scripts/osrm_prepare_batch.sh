#!/usr/bin/env bash
# Сборка OSRM foot-графов.
#   bash scripts/osrm_prepare_batch.sh           # hot
#   bash scripts/osrm_prepare_batch.sh --tier=warm
#   bash scripts/osrm_prepare_batch.sh kazan samara
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

TIER="hot"
EXPLICIT=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier=*)
      TIER="${1#--tier=}"
      shift
      ;;
    --tier)
      TIER="${2:-hot}"
      shift 2
      ;;
    *)
      EXPLICIT+=("$1")
      shift
      ;;
  esac
done

if [[ "${#EXPLICIT[@]}" -gt 0 ]]; then
  SLUGS="${EXPLICIT[*]}"
else
  SLUGS="$("$PYTHON" - "$TIER" <<'PY'
import sys
from config.city_catalog import catalog_slugs
print(" ".join(catalog_slugs(tier=sys.argv[1] or "hot")))
PY
)"
fi

if [[ -z "${SLUGS// }" ]]; then
  echo "Нет slug для prepare" >&2
  exit 1
fi

failed=0
count=0
for slug in $SLUGS; do
  count=$((count + 1))
  extract="$ROOT/data/cities/$slug/extract.osm.pbf"
  if [[ ! -f "$extract" ]]; then
    echo "SKIP $slug — нет $extract (сначала city_pack_prepare)" >&2
    failed=$((failed + 1))
    continue
  fi
  echo "=== OSRM prepare: $slug ==="
  if ! bash "$ROOT/scripts/osrm_prepare.sh" "$slug"; then
    echo "FAIL $slug" >&2
    failed=$((failed + 1))
  fi
done

if [[ "$failed" -gt 0 ]]; then
  echo "Готово с пропусками/ошибками: $failed" >&2
  exit 1
fi
echo "Все графы готовы ($count)."
