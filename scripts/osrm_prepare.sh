#!/usr/bin/env bash
# Deprecated: полный FO OSRM. Используйте city pack:
#   bash scripts/fo_ensure.sh volga
#   bash scripts/city_pack_prepare.sh kazan
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "osrm_prepare.sh устарел для runtime OSRM. Скачиваю FO PBF…" >&2
bash "$ROOT/scripts/fo_ensure.sh" volga
echo "" >&2
echo "Для маршрутов и POI:" >&2
echo "  bash scripts/city_pack_prepare.sh kazan" >&2
echo "  bash scripts/city_pack_batch.sh" >&2
echo "  docker compose --profile routing up -d osrm-gateway osrm-kazan" >&2
