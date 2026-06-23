#!/usr/bin/env bash
# Подготовка OSRM для Казани/Татарстана: Geofabrik → extract/partition/customize.
# Отдельного extract «tatarstan» на Geofabrik нет — берём Поволжский федеральный округ.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$ROOT/data/osrm"
PBF_URL="https://download.geofabrik.de/russia/volga-fed-district-latest.osm.pbf"
PBF_NAME="volga-fed-district-latest.osm.pbf"
PBF="$DATA_DIR/$PBF_NAME"
OSRM_BASE="volga-fed-district-latest"
OSRM_IMAGE="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend:latest}"
PROFILE="${OSRM_PROFILE:-foot}"
# На Apple Silicon при Illegal instruction / странных падениях:
#   DOCKER_PLATFORM=linux/amd64 bash scripts/osrm_prepare.sh
DOCKER_PLATFORM="${DOCKER_PLATFORM:-}"
MIN_PBF_BYTES=$((50 * 1024 * 1024)) # ~50 MB; volga extract ~730 MB
# Пик RAM osrm-partition/customize ~3–4 GB для Поволжского ФО
DOCKER_MEMORY="${DOCKER_MEMORY:-}"

run_osrm() {
  local -a docker_args=(run --rm -v "$DATA_DIR:/data")
  if [[ -n "$DOCKER_MEMORY" ]]; then
    docker_args+=(--memory="$DOCKER_MEMORY")
  fi
  if [[ -n "$DOCKER_PLATFORM" ]]; then
    docker_args+=(--platform "$DOCKER_PLATFORM")
  fi
  # Без -t: в некоторых терминалах Docker Desktop показывает ложное «container error».
  if docker "${docker_args[@]}" "$OSRM_IMAGE" "$@"; then
    return 0
  fi
  local code=$?
  echo "" >&2
  echo "Ошибка Docker (код $code) на шаге: $*" >&2
  if [[ "$code" -eq 137 ]]; then
    echo "Похоже на нехватку памяти (OOM). Docker Desktop → Settings → Resources → Memory ≥ 6 GB." >&2
    echo "Или: DOCKER_MEMORY=8g bash scripts/osrm_prepare.sh" >&2
  fi
  if [[ -z "$DOCKER_PLATFORM" ]] && [[ "$(uname -m)" == "arm64" ]]; then
    echo "На Apple Silicon попробуйте: DOCKER_PLATFORM=linux/amd64 bash scripts/osrm_prepare.sh" >&2
  fi
  return "$code"
}

is_valid_pbf() {
  [[ -f "$PBF" ]] || return 1
  local size
  size="$(wc -c <"$PBF" | tr -d ' ')"
  [[ "$size" -ge "$MIN_PBF_BYTES" ]] || return 1
  local head_bytes
  head_bytes="$(head -c 16 "$PBF" 2>/dev/null || true)"
  [[ "$head_bytes" != "<!DOCTYPE html>"* ]] || return 1
  [[ "$head_bytes" != "<html"* ]] || return 1
  return 0
}

osrm_ready() {
  [[ -f "$DATA_DIR/${OSRM_BASE}.osrm.mldgr" ]] \
    && [[ -f "$DATA_DIR/${OSRM_BASE}.osrm.partition" ]] \
    && [[ -f "$DATA_DIR/${OSRM_BASE}.osrm.edges" ]]
}

extract_ready() {
  [[ -f "$DATA_DIR/${OSRM_BASE}.osrm.edges" ]]
}

partition_ready() {
  [[ -f "$DATA_DIR/${OSRM_BASE}.osrm.partition" ]]
}

mkdir -p "$DATA_DIR"

if [[ "${FORCE_DOWNLOAD:-}" == "1" ]] || ! is_valid_pbf; then
  if [[ -f "$PBF" ]]; then
    echo "Удаляю повреждённый или устаревший файл: $PBF"
    rm -f "$PBF"
    rm -f "$DATA_DIR/${OSRM_BASE}.osrm" "$DATA_DIR/${OSRM_BASE}.osrm."*
  fi
  echo "Скачивание $PBF_URL (~730 MB, 5–20 мин) ..."
  curl -L --fail --retry 3 --retry-delay 5 -o "$PBF" "$PBF_URL"
fi

if ! is_valid_pbf; then
  echo "Ошибка: после скачивания файл не похож на .osm.pbf (слишком маленький или HTML)." >&2
  echo "Проверьте URL и сеть. Размер: $(wc -c <"$PBF" | tr -d ' ') байт" >&2
  exit 1
fi

if osrm_ready && [[ "${FORCE_REBUILD:-}" != "1" ]]; then
  echo "OSRM уже подготовлен в $DATA_DIR"
  echo "Пересборка: FORCE_REBUILD=1 bash scripts/osrm_prepare.sh"
  echo "Запуск: docker compose --profile routing up -d osrm"
  exit 0
fi

echo "Файл: $PBF ($(du -h "$PBF" | cut -f1))"
echo "Образ: $OSRM_IMAGE"
[[ -n "$DOCKER_PLATFORM" ]] && echo "Платформа: $DOCKER_PLATFORM"
[[ -n "$DOCKER_MEMORY" ]] && echo "Лимит памяти контейнера: $DOCKER_MEMORY"

if extract_ready && [[ "${FORCE_EXTRACT:-}" != "1" ]] && [[ "${FORCE_REBUILD:-}" != "1" ]]; then
  echo "osrm-extract — пропуск (уже есть ${OSRM_BASE}.osrm.edges)"
else
  echo "osrm-extract ($PROFILE) … (5–15 мин, в конце: Node/Edge compression ratio)"
  run_osrm osrm-extract -p "/opt/${PROFILE}.lua" "/data/$PBF_NAME"
fi

if partition_ready && [[ "${FORCE_REBUILD:-}" != "1" ]]; then
  echo "osrm-partition — пропуск"
else
  echo "osrm-partition … (нужно ~3–4 GB RAM, 2–10 мин)"
  run_osrm osrm-partition "/data/${OSRM_BASE}.osrm"
fi

echo "osrm-customize …"
run_osrm osrm-customize "/data/${OSRM_BASE}.osrm"

echo ""
echo "Готово. Запуск: docker compose --profile routing up -d osrm"
echo "Проверка: curl -s 'http://127.0.0.1:5001/route/v1/foot/47.89,56.63;47.90,56.64?overview=false' | head -c 120"
