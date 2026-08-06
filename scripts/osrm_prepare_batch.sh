#!/usr/bin/env bash
# Сборка OSRM foot-графов для всех default_packs (или списка slug).
# Использование:
#   bash scripts/osrm_prepare_batch.sh
#   bash scripts/osrm_prepare_batch.sh kazan samara
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

if [[ "$#" -gt 0 ]]; then
  SLUGS="$*"
else
  SLUGS="$("$PYTHON" - <<'PY'
from config.city_catalog import load_city_pack_specs
for slug, spec in load_city_pack_specs().items():
    if spec.is_default:
        print(slug)
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
