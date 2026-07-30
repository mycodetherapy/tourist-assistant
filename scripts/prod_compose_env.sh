# shellcheck shell=bash
# Общие переменные для prod compose на VPS. Source: . scripts/prod_compose_env.sh

_prod_root() {
  if [[ -n "${DEPLOY_DIR:-}" ]]; then
    echo "$DEPLOY_DIR"
  elif [[ -f "$(dirname "${BASH_SOURCE[0]}")/../docker-compose.prod.yml" ]]; then
    cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
  elif [[ -f ./docker-compose.prod.yml ]]; then
    pwd
  else
    echo "${DEPLOY_DIR:-/opt/tourist-assistant}"
  fi
}

PROD_DEPLOY_DIR="$(_prod_root)"
PROD_COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
PROD_ENV_FILE="${PROD_DEPLOY_DIR}/.env"
PROD_TAG_FILE="${PROD_DEPLOY_DIR}/.deploy-image-tag"

if [[ -z "${IMAGE_TAG:-}" && -f "$PROD_TAG_FILE" ]]; then
  IMAGE_TAG="$(tr -d '[:space:]' < "$PROD_TAG_FILE")"
  export IMAGE_TAG
fi

prod_compose() {
  if [[ -z "${IMAGE_TAG:-}" ]]; then
    echo "ERROR: IMAGE_TAG not set. Deploy via CI or: export IMAGE_TAG=latest" >&2
    echo "Last tag file: $PROD_TAG_FILE" >&2
    return 1
  fi
  docker compose --env-file "$PROD_ENV_FILE" -f "${PROD_DEPLOY_DIR}/${PROD_COMPOSE_FILE}" "$@"
}
