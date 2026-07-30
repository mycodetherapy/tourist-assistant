#!/usr/bin/env bash
# Статус prod-контейнеров на VPS (обёртка с IMAGE_TAG из .deploy-image-tag).
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/tourist-assistant}"
cd "$DEPLOY_DIR"
# shellcheck source=prod_compose_env.sh
source "$(dirname "$0")/prod_compose_env.sh"

echo "IMAGE_TAG=${IMAGE_TAG:-?}"
prod_compose ps
