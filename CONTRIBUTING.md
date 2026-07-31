# Разработка и релизы

## Ветки

| Ветка | Назначение |
|-------|------------|
| `develop` | Интеграционная ветка для ежедневной разработки |
| `main` | Стабильный релиз; только через PR после зелёного CI |
| `feat/*`, `fix/*` | Короткоживущие ветки от `develop` |

## Поток изменений

1. Создайте ветку от `develop`: `git checkout develop && git pull && git checkout -b feat/my-feature`
2. Откройте **PR в `develop`** — CI **не** запускается; при необходимости прогоните [локальные проверки](#локальные-проверки-перед-pr).
3. После ревью смержите в `develop`.
4. Для релиза откройте **PR `develop` → `main`** — запустится [CI](.github/workflows/ci.yml) (тесты + smoke-сборка Docker). После merge в `main`:
   - [Deploy](.github/workflows/deploy.yml) собирает образы, пушит в **GHCR** и обновляет VPS.

## Защита веток (GitHub)

Рекомендуемые правила для `main` (Settings → Branches):

- Require pull request before merging
- Require status checks: **Python tests**, **api-node tests**, **web build**, **Docker build smoke**
- Do not allow bypassing (для админов — по желанию)

Для `develop`:

- Require pull request (опционально)
- Status checks CI **не обязательны** (CI только на PR в `main`)

## Локальные проверки перед PR

```bash
docker compose up -d postgres redis
export DATABASE_URL=postgresql+psycopg://tourist:tourist@localhost:5433/tourist
export TEST_DATABASE_URL=postgresql+psycopg://tourist:tourist@localhost:5433/tourist_test
python scripts/ensure_test_database.py
python -m unittest discover -s tests -v

cd api-node && npm ci && npm run build && npm test
cd ../web && npm ci && npm run build
```

## CI/CD

Подробности prod-деплоя: раздел [CI/CD и продакшен](README.md#cicd-и-продакшен) в README.
