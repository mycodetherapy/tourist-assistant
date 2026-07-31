#!/usr/bin/env bash
# Единая команда статистики: ./stats.sh [subcommand] [args…]
# Работает на VPS (prod Docker), локально (dev Docker) и в .venv.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_find_root() {
  if [[ -f "$SCRIPT_DIR/docker-compose.prod.yml" || -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
    echo "$SCRIPT_DIR"
    return
  fi
  if [[ -f "$SCRIPT_DIR/../docker-compose.prod.yml" || -f "$SCRIPT_DIR/../docker-compose.yml" ]]; then
    (cd "$SCRIPT_DIR/.." && pwd)
    return
  fi
  echo "$SCRIPT_DIR"
}

usage() {
  cat <<'EOF'
Usage: stats.sh [command] [options]

  summary                  сводка (по умолчанию)
  registrations [--days N]
  logins [--days N]
  online [--minutes N]
  activity [--limit N]
  user --email ADDR | --id N

Examples:
  ./stats.sh
  ./stats.sh online --minutes 15
  ./stats.sh user --email user@example.com
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ARGS=("$@")
if ((${#ARGS[@]} == 0)); then
  ARGS=(summary)
fi

ROOT="$(_find_root)"
cd "$ROOT"

PY_SCRIPT="scripts/admin_stats.py"

_run_in_container() {
  docker exec -i "$1" python "$PY_SCRIPT" "${ARGS[@]}"
}

_worker_container_id() {
  docker ps -q \
    --filter "label=com.docker.compose.service=worker" \
    --filter "status=running" 2>/dev/null | head -1 || true
}

_try_prod() {
  [[ -f "$ROOT/docker-compose.prod.yml" ]] || return 1
  [[ -f "$ROOT/.deploy-image-tag" || -n "${IMAGE_TAG:-}" ]] || return 1
  local env_sh=""
  for candidate in "$ROOT/prod_compose_env.sh" "$SCRIPT_DIR/prod_compose_env.sh"; do
    if [[ -f "$candidate" ]]; then
      env_sh="$candidate"
      break
    fi
  done
  [[ -n "$env_sh" ]] || return 1
  # shellcheck source=/dev/null
  source "$env_sh"
  prod_compose exec -T worker python "$PY_SCRIPT" "${ARGS[@]}"
}

_try_dev_compose() {
  [[ -f "$ROOT/docker-compose.yml" ]] || return 1
  docker compose --env-file "$ROOT/.env" -f "$ROOT/docker-compose.yml" exec -T worker \
    python "$PY_SCRIPT" "${ARGS[@]}"
}

_try_venv() {
  [[ -x "$ROOT/.venv/bin/python" ]] || return 1
  "$ROOT/.venv/bin/python" "$ROOT/$PY_SCRIPT" "${ARGS[@]}"
}

if _try_prod; then exit 0; fi

cid="$(_worker_container_id)"
if [[ -n "$cid" ]]; then
  _run_in_container "$cid"
  exit 0
fi

if _try_dev_compose; then exit 0; fi
if _try_venv; then exit 0; fi

cat >&2 <<EOF
ERROR: не удалось запустить статистику.

Проверьте:
  • VPS:  cd /opt/tourist-assistant && ./stats.sh summary
  • worker должен быть Up: docker ps | grep worker

ROOT=$ROOT
EOF
exit 1
