# Прогуляй (progulyai.ru)

**Сразу попробовать:** [https://progulyai.ru](https://progulyai.ru) — регистрация, три маршрута A/B/C и карта в браузере, без установки.

[![CI](https://github.com/mycodetherapy/tourist-assistant/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mycodetherapy/tourist-assistant/actions/workflows/ci.yml)

**Прогуляй** — веб-сервис пеших прогулок по городу: три альтернативных маршрута A/B/C на основе пула POI из **Wikidata/OSM**, с deep link в Яндекс.Карты и блоком **«О городе»** (Wikipedia/Wikidata → LLM, 6–8 предложений с историческими фактами). Центральная функция — маршруты и базовая точка старта (`route_anchor`). Прогулки, предпочтения и версии программы хранятся в **PostgreSQL**.

## Статус и планы

Приложение находится **в стадии активной разработки**. Текущая версия — **routes-first MVP**: сервис собирает три маршрута; **факт о городе** подгружается **параллельно** (маршруты показываются сразу, блок «О городе» — по готовности). **Веб-интерфейс и REST API** на [progulyai.ru](https://progulyai.ru) позволяют создавать прогулки и пересобирать маршруты. Консольный CLI снят.

**Ближайшие планы:**

| Направление  | Что планируется                                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| **Маршруты** | City pack (OSM PBF → `poi.sqlite`) для 8 городов Поволжья; карта маршрута — iframe Яндекс.Карт               |
| **SaaS**     | Многопользовательский режим: регистрация, личный кабинет, изоляция поездок по аккаунту (Postgres + Node API) |

## Быстрый старт

### Требования

- Python **3.10+** (работает на 3.9+)
- API-ключ **LLM-провайдера** (по умолчанию [ProxyAPI](https://proxyapi.ru); также OpenRouter и др.)

### Быстрый старт (Docker)

```bash
git clone <url-репозитория>
cd tourist-assistant

test -f .env || cp .env.example .env
# DATABASE_URL, REDIS_URL, JWT_SECRET, SETTINGS_ENCRYPTION_KEY — обязательны

docker compose up -d --build
# UI в Docker (без npm run dev): docker compose --profile docker-web up -d --build
```

UI: [http://localhost:5173](http://localhost:5173) — **локальный** `npm run dev` в `web/` (см. ниже) или контейнер `web` с профилем `docker-web`. API health: [http://localhost:8001/api/health](http://localhost:8001/api/health).

### Локальная разработка (API + React)

Требования: Python 3.10+, Node.js 20+, Postgres и Redis. В `.env`: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `SETTINGS_ENCRYPTION_KEY` (см. `.env.example`). API-ключ LLM каждый пользователь задаёт в **Настройках** (BYOK). Для `python -m eval --with-llm` нужен `LLM_API_KEY` в `.env`.

**Инфра + API + worker в Docker, фронт локально (рекомендуется для разработки UI):**

```bash
docker compose up -d --build   # без web — порт 5173 свободен для Vite
cd web && npm install && npm run dev
```

**Инфра (терминал 0) — если всё на хосте без Docker API/worker:**

```bash
docker compose up -d postgres redis
export DATABASE_URL=postgresql+psycopg://tourist:tourist@localhost:5433/tourist
export REDIS_URL=redis://localhost:6380/0
alembic upgrade head
```

**Терминал 1 — worker (LangGraph):**

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m worker
```

**Терминал 2 — Node API:**

```bash
cd api-node
npm install
npm run dev
```

**Терминал 3 — фронтенд:**

```bash
cd web
npm install
npm run dev
```

Откройте **https://localhost:5173** (Vite dev — HTTPS; `http://` не работает). Vite проксирует `/api` на `http://127.0.0.1:8001` (api-node). На главной (`/`) — лендинг **Прогуляй**; для работы нужны **регистрация** (`/register`) или **вход** (`/login`, в т.ч. Google OAuth), затем в **Настройках** — API-ключ LLM (Base URL, модель). Список прогулок — `/trips`.

**Проверка с телефона (PWA):**

1. Mac и телефон в одной Wi‑Fi; запустите API и `npm run dev` (как выше).
2. В выводе Vite найдите строку **Phone / PWA dev URL** (`https://192.168.x.x:5173`) или узнайте IP: `ipconfig getifaddr en0`.
3. Откройте **HTTPS**-адрес **в Safari/Chrome** (не через иконку «На экран Домой», если раньше добавляли `localhost`). При первом заходе браузер попросит доверять dev-сертификату — без HTTPS геолокация на карте стартовой точки не работает.
4. **macOS:** если не открывается — **Системные настройки → Сеть → Брандмауэр → Параметры** → для **node** выберите «Разрешить входящие подключения».
5. **Чёрный экран:** перезапустите `npm run dev` (Vite прописывает HMR на IP Mac). На iPhone: Настройки → Safari → «Дополнения» → «Данные веб-сайтов» → удалите сайт `192.168.x.x`. Не используйте гостевую Wi‑Fi (изоляция клиентов).
6. Установка на главный экран: Android — «Установить приложение»; iPhone — «Поделиться» → «На экран Домой» (после того как сайт открылся в Safari по IP).
7. **Геолокация:** только при **новой прогулке** — выбор стартовой точки на `ymaps.Map` (`VITE_YANDEX_MAPS_API_KEY`, HTTPS с телефона). Карта маршрута — iframe без геолокации.
8. **Google OAuth:** при HTTPS dev callback — `https://<host>:5173/api/auth/google/callback` (добавьте URI в Google Cloud Console; origin передаётся автоматически).

### City pack (POI из OSM-выжимки)

POI строятся из `extract.osm.pbf` на город ([`config/city_packs.yaml`](config/city_packs.yaml)). Статусы каталога — таблица `city_packs` в Postgres. **Pack готов** → POI из OSM; **pack не готов или пустой** → Wikidata; оба пусты → demo. Карта маршрута — **iframe-виджет** Яндекса по `maps_route_url` (пеший режим `rtt=pd`).

**Первый запуск (Поволжский ФО, 8 городов):**

```bash
bash scripts/fo_ensure.sh volga              # FO PBF ~730 MB (один раз)
bash scripts/city_pack_prepare.sh kazan      # extract + poi.sqlite (~2–4 мин)
bash scripts/city_pack_prepare.sh yoshkar-ola
# или все default packs:
bash scripts/city_pack_batch.sh
```

При первом `city_pack_prepare` автоматически собирается Docker-образ `local-osmium-tool` (`scripts/Dockerfile.osmium`), если нет доступа к `ghcr.io/osmcode/osmium-tool`.

Каталог городов: [`config/city_packs.yaml`](config/city_packs.yaml); федеральные округа (Geofabrik): [`config/federal_districts.yaml`](config/federal_districts.yaml). Новый город — запись в YAML + `city_pack_prepare.sh` + `alembic upgrade head` (синхронизация `city_packs`).

Города **в каталоге** без готового pack — worker ставит prepare в очередь, POI берутся из **Wikidata** до готовности pack. Если и OSM, и Wikidata пусты — demo-точки. `pip install osmium` нужен для `build_poi_index.py`.

Для стабильного PWA-теста без dev-сервера: `cd web && npm run build && npm run preview -- --host`.

Без открытия портов: `cloudflared tunnel --url http://localhost:5173`. Через Docker: `docker compose up` → `http://<IP-Mac>:5173`.

**API:** Node.js Fastify на порту **8001** (`api-node/`).

**Swagger (живой, из кода):**

- Локально (api-node): [http://localhost:8001/docs](http://localhost:8001/docs)
- Prod (через nginx web): [https://progulyai.ru/docs](https://progulyai.ru/docs)
- JSON: `/docs/json` на том же хосте

После первого деплоя с прокси `/docs`: если открывается лендинг в обычной вкладке, а в инкогнито — Swagger, очистите данные сайта (Service Worker PWA кэшировал старый `index.html`). Либо дождитесь обновления PWA с `navigateFallbackDenylist` для `/docs`.

На `:5173/docs` (Vite dev) откроется SPA, не Swagger — используйте `:8001/docs` или prod-домен после деплоя web-образа.

Схема в репозитории (`docs/openapi.json`) генерируется из тех же маршрутов:

```bash
python3 scripts/export_openapi.py
# или: cd api-node && npm run export:openapi
```

Pre-commit hook (`./scripts/install_git_hooks.sh`) обновляет `docs/openapi.json` автоматически.

**Базовая точка маршрута:** отель или адрес проживания задаётся в мастере новой поездки или в карточке поездки (аккордеон «Базовая точка маршрута», по умолчанию свёрнут; скрывается на время сборки/пересборки). API: `PUT /api/trips/{id}/preferences` (`route_anchor`), геокодинг `POST /api/trips/geocode` и `POST /api/trips/{id}/geocode`, обратный геокодинг `POST /api/trips/reverse-geocode` и `POST /api/trips/{id}/reverse-geocode`, центр города `GET /api/trips/{id}/city-center`. На фронте — JavaScript API Яндекс.Карт (`VITE_YANDEX_MAPS_API_KEY` в корневом `.env` или `web/.env`); на бэкенде — `YANDEX_MAPS_API_KEY`. После изменения точки пересбор **только вручную** — «Пересобрать» с областью `routes`. На мобильной вкладке «Маршруты» — переключатель A/B/C (один вариант на экран); на десктопе — три карточки списком.

Один раз установить автообновление схемы перед коммитом:

```bash
./scripts/install_git_hooks.sh
```

| Экран                  | Действие                                                                                                                                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Вход / регистрация** | Email+пароль или Google; JWT в `localStorage`                                                                                                                                                                                                   |
| **Настройки**          | BYOK: API key LLM, Base URL, модель (шифруется в Postgres)                                                                                                                                                                                      |
| **Список прогулок**    | Только прогулки текущего пользователя                                                                                                                                                                                                           |
| **Новая прогулка**     | Wizard: город → запуск → фоновая сборка (polling 1–2 мин)                                                                                                                                                                                       |
| **Карточка прогулки**  | Единая страница маршрутов (A/B/C) с **встроенной картой** + базовая точка; **клик по остановке** → модалка со справкой (on-demand, polling); внизу **«О городе»** (skeleton, пока `city_fact_status=pending`); пересбор маршрутов одной кнопкой |

Docker (веб + API): см. [Запуск в Docker](#запуск-в-docker-docker-compose).

**Оценки пунктов (👍/👎):** для **вариантов маршрута и остановок** (блок «О городе» без голосования). Веб: клик → `PUT /api/trips/{id}/program/feedback`. Хранение: `program_item_feedback` (Postgres). **👎 на остановку** — жёсткий запрет `poi_id` при пересборке (дизлайк сохраняется между прогонами); похожие места (тот же мотив/имя, напр. собор и памятник Ушакова) тоже исключаются. **👎 на вариант маршрута** — мягкая подсказка LLM + бан остановок этого варианта.

### Запуск в Docker (Docker Compose)

Требования: [Docker](https://docs.docker.com/get-docker/) и Docker Compose v2.

#### VPS (Timeweb): Docker Hub 429 / блокировка

На серверах Timeweb Cloud при `docker compose build` возможна ошибка `429 Too Many Requests` или `403 Forbidden` при pull с `docker.io`. Подключите [прокси Timeweb](https://dockerhub.timeweb.cloud/):

```bash
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": ["https://dockerhub.timeweb.cloud"]
}
EOF
sudo systemctl restart docker
docker compose --profile docker-web up -d --build
```

Опционально: `docker login` (бесплатный аккаунт Docker Hub) — выше лимит pull. Явный pull через прокси: `docker pull dockerhub.timeweb.cloud/library/node:22-alpine`.

### CI/CD и продакшен

Исходники — **открытый GitHub**. Продакшен работает на **готовых Docker-образах** из приватного **GHCR**, без `git pull` и без сборки на VPS.

| Этап                    | Что происходит                                                                                                 |
| ----------------------- | -------------------------------------------------------------------------------------------------------------- |
| PR → `main`      | [`.github/workflows/ci.yml`](.github/workflows/ci.yml): Python-тесты, api-node, сборка web, smoke Docker build |
| Push → `develop` | CI **не** запускается (только локальные проверки или PR в `main`)                                              |
| Merge → `main`          | [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml): push образов в GHCR + SSH-деплой на VPS        |
| VPS                     | `docker compose -f docker-compose.prod.yml pull` и перезапуск (`scripts/deploy_prod.sh`)                       |

**Ветки:** разработка в `develop`, стабильный релиз — только `main` через PR ([CONTRIBUTING.md](CONTRIBUTING.md)).

**Образы в GHCR** (приватные, тег = git SHA + `main` + `latest`):

- `ghcr.io/mycodetherapy/tourist-assistant-worker`
- `ghcr.io/mycodetherapy/tourist-assistant-api-node`
- `ghcr.io/mycodetherapy/tourist-assistant-web`

#### Секреты GitHub Actions

В репозитории: **Settings → Secrets and variables → Actions**:

| Secret                     | Назначение                                                                                                            |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `VPS_HOST`                 | IP или домен VPS (например `185.39.206.213`)                                                                          |
| `VPS_USER`                 | SSH-пользователь (`root` или deploy-user)                                                                             |
| `VPS_SSH_KEY`              | Приватный ключ SSH (полное содержимое)                                                                                |
| `GHCR_USER`                | GitHub **username** владельца пакетов (обычно `mycodetherapy`)                                                        |
| `GHCR_READ_TOKEN`          | Classic PAT с scope **`read:packages`** (или fine-grained: Packages → Read). Без него pull на VPS → **403 Forbidden** |
| `VITE_YANDEX_MAPS_API_KEY` | Ключ Яндекс.Карт для **сборки** web в CI                                                                              |

Packages → каждый образ → **Change visibility → Private** (если репозиторий публичный).

**Deploy падает с `403 Forbidden` на `ghcr.io/.../tourist-assistant-worker`:**

1. В **Settings → Secrets → Actions** должны быть заданы **`GHCR_USER`** и **`GHCR_READ_TOKEN`** (не пустые).
2. PAT: [github.com/settings/tokens](https://github.com/settings/tokens) → **read:packages**; для org — Authorize SSO у токена.
3. Проверка на VPS вручную:
   ```bash
   echo "$TOKEN" | docker login ghcr.io -u mycodetherapy --password-stdin
   docker pull ghcr.io/mycodetherapy/tourist-assistant-worker:main
   ```
4. У пакета в GHCR: **Package settings → Manage Actions access** — репозиторий `tourist-assistant` имеет доступ (или PAT от владельца пакетов).

#### Первичная настройка VPS (один раз)

```bash
sudo mkdir -p /opt/tourist-assistant/data
sudo cp deploy/env.example /opt/tourist-assistant/.env
# Заполните JWT_SECRET, SETTINGS_ENCRYPTION_KEY, FRONTEND_URL, CORS_ORIGINS, POSTGRES_PASSWORD, …
sudo docker login ghcr.io -u <GHCR_USER> -p <GHCR_READ_TOKEN>
```

Существующий `.env` с `docker-compose.yml` можно оставить: добавьте `POSTGRES_PASSWORD=…` (на prod — **обязательно**, минимум 16 символов, не `tourist`). Для OAuth укажите `FRONTEND_URL=https://progulyai.ru` и `CORS_ORIGINS=https://progulyai.ru,https://www.progulyai.ru`, а также `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`. Дальнейшие релизы — только через CI после merge в `main`.

Смена пароля Postgres на работающем prod:

```bash
cd /opt/tourist-assistant
NEW_POSTGRES_PASSWORD='…' bash rotate_postgres_password.sh
```

`deploy_prod.sh` не пропустит деплой с `POSTGRES_PASSWORD=tourist` или `FRONTEND_URL=localhost`.

Если email-login или Google OAuth падают с 500 — на VPS проверьте миграции и логи:

```bash
cd /opt/tourist-assistant
docker compose -f docker-compose.prod.yml exec -T worker alembic current   # head: c4e1f8a92d10
docker compose -f docker-compose.prod.yml exec -T worker alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --force-recreate worker api-node
docker compose -f docker-compose.prod.yml logs api-node --tail 80
```

Колонка `users.last_seen_at` нужна для audit при входе (ревизия `c4e1f8a92d10`). Worker применяет `alembic upgrade head` при каждом старте; при отставании схемы — команды выше.

Ручной деплой с сервера (если нужно):

```bash
cd /opt/tourist-assistant
IMAGE_TAG=<git-sha> ./deploy_prod.sh
```

Локальная разработка по-прежнему через `docker compose up --build` в корне репозитория.

#### Первый запуск

```bash
cd tourist-assistant

# Создать .env только если файла ещё нет:
./scripts/ensure_env_file.sh
# или: test -f .env || cp .env.example .env

# Заполните .env в редакторе (LLM_API_KEY и др.)

# Права только для вашего пользователя (рекомендуется):
chmod 600 .env

docker compose build
docker compose up -d
```

UI: [http://localhost:5173](http://localhost:5173), API: [http://localhost:8001/api/health](http://localhost:8001/api/health).

#### Тесты в Docker

```bash
docker compose run --rm worker python -m unittest discover -s tests -v
docker compose run --rm worker python -m eval --suite smoke
```

**Важно:** unit-тесты с Postgres делают `TRUNCATE` только в `TEST_DATABASE_URL` (БД с суффиксом `_test`, по умолчанию `tourist_test`). В `.env` должны быть обе переменные; test-БД создаётся `python3 scripts/ensure_test_database.py`. Не запускайте тесты без `TEST_DATABASE_URL` — иначе они пропускаются. Не используйте `docker compose down -v` на dev-данных.

Скрипт `ensure_env_file.sh` и `test -f .env || cp …` **не трогают** существующий `.env`.

#### Postgres + Redis (локально без полного compose)

```bash
docker compose up -d postgres redis

export DATABASE_URL=postgresql+psycopg://tourist:tourist@localhost:5433/tourist
export REDIS_URL=redis://localhost:6380/0
alembic upgrade head

python3 -m unittest tests.test_postgres_schema -v
python3 -m unittest tests.test_db_postgres -v
python3 -m unittest tests.test_graph_runs -v

python -m worker
cd api-node && npm run dev
```

Тесты Node: `cd api-node && npm test`. Интеграционные (нужен `DATABASE_URL`): `npm run test:integration` — auth, изоляция поездок, BYOK 428, anti-injection.

**Parity с бывшим FastAPI:** геокодинг с `poi_filters` и Nominatim fallback; `sanitize_and_validate` на создании поездки; `GET /api/trips/{id}/program` вызывает `scripts/repair_program_cli.py` (тот же `repair_program_routes`, что в `trip_service`). Локально нужен `.venv`; в Docker — `Dockerfile.api-node` (образ Python + Node в одном контейнере).

**Repair в Docker:** образ `api-node` включает Python-код для `repair_program_cli`. После изменений в `agents/`, `search/`, `scripts/repair_program_cli.py` нужна пересборка: `docker compose build api-node`. Альтернативы — см. [Repair program в Docker](#repair-program-в-docker).

Фоновые прогоны: **JSON Redis queue** (`tourist:queue:*`, `worker/tasks.py`, таблица `graph_runs`).

Бэкап prod (cron на VPS): [`scripts/pg_backup.sh`](scripts/pg_backup.sh).

### Repair program в Docker

`GET /api/trips/{id}/program` вызывает Python `repair_program_routes` через subprocess (`scripts/repair_program_cli.py`). В production-образе `api-node` (`Dockerfile.api-node`) лежат и Node API, и нужные Python-модули (`agents/`, `search/`, …).

**Что значит «нужна пересборка»:** Docker-образ — снимок файлов на момент `docker compose build`. Если вы меняете Python-логику repair локально, контейнер продолжает работать со **старым** кодом внутри образа, пока вы не пересоберёте и не перезапустите:

```bash
docker compose build api-node && docker compose up -d api-node
```

Локально (`npm run dev`) repair берёт код с диска — пересборка не нужна.

| Подход                                               | Плюсы                                             | Минусы                                                    |
| ---------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------- |
| **Текущий: гибридный образ** (`Dockerfile.api-node`) | Полный parity с Python; один контейнер            | Больший образ; rebuild при изменении Python repair        |
| **Чистый Node-образ + HTTP к worker**                | Маленький api-node; repair всегда свежий в worker | Нужен внутренний endpoint на worker; сеть между сервисами |
| **Чистый Node + volume mount Python** (только dev)   | Без rebuild в dev                                 | Не для prod; хрупко                                       |
| **Порт repair на TypeScript**                        | Один runtime в api-node                           | Дублирование ~1000 строк `route_postprocess`              |
| **Отдельный микросервис `repair`**                   | Изоляция                                          | Ещё один деплой                                           |

Для prod сейчас оптимален гибридный образ; при частых правках repair удобнее вынести HTTP-вызов на worker (тот же код, без копии в api-node).

### Тесты и eval (без полного прогона агента)

Перед первым запуском Postgres-тестов локально:

```bash
python3 scripts/ensure_test_database.py
```

В `.env` укажите `TEST_DATABASE_URL=…/tourist_test` (отдельно от `DATABASE_URL=…/tourist`). Тесты **никогда** не делают `TRUNCATE` на dev-БД без `ALLOW_TEST_TRUNCATE=1`.

Запускайте **по одной строке** (не копируйте `#` в конце строки — shell воспримет это как аргумент).

```bash
python3 -m unittest discover -s tests -v
```

```bash
python3 -m eval --suite smoke
```

С LLM-judge (нужен `LLM_API_KEY`):

```bash
python3 -m eval --suite smoke --with-llm
```

Eval проверяет **fixtures** в `eval/fixtures/` (схема программы, tool_runs, regression к `eval/golden/`), а не живой интернет.

### Переменные окружения

Шаблон: [`.env.example`](.env.example) (совпадает с типовым локальным `.env`).

| Переменная                                  | Обязательно | Описание                                                                                                                       |
| ------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `LLM_API_KEY`                               | Нет\*       | Для `python -m eval --with-llm` и dev-скриптов; веб-API использует BYOK в профиле                                              |
| `JWT_SECRET`                                | Да\*\*      | Секрет подписи JWT (api-node)                                                                                                  |
| `SETTINGS_ENCRYPTION_KEY`                   | Да\*\*      | Fernet-ключ шифрования BYOK в БД (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `JWT_ACCESS_TTL_MINUTES`                    | Нет         | Срок жизни access token (по умолчанию 60)                                                                                      |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Нет         | Google OAuth (опционально). Один OAuth client — несколько **Authorized redirect URIs** в Google Console                        |
| `GOOGLE_REDIRECT_URI`                       | Нет         | Fallback; в OAuth `redirect_uri` = `{origin фронта}/api/auth/google/callback` (см. ниже)                                       |
| `FRONTEND_URL`                              | Нет         | Origin фронта (prod: `https://progulyai.ru`; локально: `https://localhost:5173` при HTTPS dev)                                 |
| `CORS_ORIGINS`                              | Нет         | Доп. origins через запятую; для OAuth — тот же домен, что и `FRONTEND_URL` на проде                                            |
| `LLM_BASE_URL`                              | Нет         | OpenAI-compatible endpoint, по умолчанию `https://openai.api.proxyapi.ru/v1`                                                   |
| `LLM_MODEL`                                 | Нет         | Slug модели. По умолчанию `gemini/gemini-2.5-flash` (см. [Модели LLM](#модели-llm))                                            |
| `LLM_OPENROUTER_PROVIDERS`                  | Нет         | **Только worker**, и **только** если Base URL содержит `openrouter.ai`. При ProxyAPI (`openai.api.proxyapi.ru`) игнорируется   |
| `DATABASE_URL`                              | Да\*\*      | PostgreSQL (обязателен для API и worker)                                                                                       |
| `TEST_DATABASE_URL`                         | Для тестов  | Отдельная БД `tourist_test` для `unittest` (`TRUNCATE`); создаётся `scripts/ensure_test_database.py`                           |
| `REDIS_URL`                                 | Да\*\*      | Redis: JSON worker queue, locks, лимиты прогонов                                                                               |
| `LANGCHAIN_TRACING_V2`                      | Нет         | `true` — трейсы в [LangSmith](https://smith.langchain.com)                                                                     |
| `LANGCHAIN_API_KEY`                         | Нет         | Ключ LangSmith                                                                                                                 |
| `LANGCHAIN_PROJECT`                         | Нет         | Имя проекта (по умолчанию `tourist-assistant`)                                                                                 |
| `LANGSMITH_ENDPOINT`                        | Нет         | Кастомный endpoint LangSmith (опционально)                                                                                     |
| `LANGFUSE_ENABLED`                          | Нет         | `true` — включить трейсы в LangFuse (self-hosted)                                                                              |
| `LANGFUSE_HOST`                             | Нет         | LangFuse, например `http://localhost:3000`                                                                                     |
| `LANGFUSE_HOST_DOCKER`                      | Нет         | LangFuse для Docker, например `http://host.docker.internal:3000`                                                               |
| `LANGFUSE_PUBLIC_KEY`                       | Нет         | Public key проекта LangFuse                                                                                                    |
| `LANGFUSE_SECRET_KEY`                       | Нет         | Secret key проекта LangFuse                                                                                                    |

**Дополнительно** (дефолты в коде, в `.env.example` нет): `TAVILY_API_KEY` (иначе `ddgs`, ru-ru); `VITE_YANDEX_MAPS_API_KEY` (корневой `.env` или `web/.env`, карта стартовой точки); `VITE_DEV_HTTPS` (HTTPS dev для геолокации с телефона); `POI_USE_WIKIDATA`, `POI_USE_DISCOVERY`; `NOMINATIM_URL`, `NOMINATIM_USER_AGENT`; `YANDEX_MAPS_API_KEY` (HTTP Geocoder на бэкенде).

#### Google OAuth (prod + local)

Фронт передаёт `?frontend=` (текущий `window.location.origin`); api-node строит callback `{origin}/api/auth/google/callback`. В **Google Cloud Console → OAuth client → Authorized redirect URIs** укажите **оба** (один client на prod и dev):

| Окружение               | Redirect URI                                                                                   |
| ----------------------- | ---------------------------------------------------------------------------------------------- |
| **Prod**                | `https://progulyai.ru/api/auth/google/callback`                                                |
| **Local HTTPS dev**     | `https://localhost:5173/api/auth/google/callback`                                              |
| **Local LAN (телефон)** | `https://<IP-вашего-Mac>:5173/api/auth/google/callback` — только если входите с телефона по IP |

Строка должна **совпадать посимвольно** (https, без слэша в конце, порт `:5173`). Старые `http://localhost:5173/...` или `http://localhost:8001/...` **не подходят**, если Vite на HTTPS.

**Ошибка `redirect_uri_mismatch`:** откройте ссылку «Войти через Google», в адресной строке Google найдите `redirect_uri=` — этот URI добавьте в Console. На Mac чаще всего не хватает `https://localhost:5173/...`; при входе с телефона по IP — добавьте URI с вашим `192.168.x.x`.

**Безопасность:** параметр `?frontend=` и cookie `oauth_frontend` принимаются только из whitelist (`FRONTEND_URL`, `CORS_ORIGINS`, localhost / 127.0.0.1 / LAN IPv4). Произвольные домены (например `attacker.com`) отклоняются — редирект с JWT идёт на `FRONTEND_URL`.

### Модели LLM

#### ProxyAPI (по умолчанию) vs OpenRouter

|                            | **ProxyAPI** (дефолт)                 | **OpenRouter** (альтернатива)                                  |
| -------------------------- | ------------------------------------- | -------------------------------------------------------------- |
| `LLM_BASE_URL`             | `https://openai.api.proxyapi.ru/v1`   | `https://openrouter.ai/api/v1`                                 |
| `LLM_MODEL`                | `gemini/gemini-2.5-flash`             | например `openai/gpt-4.1-mini` или `google/gemini-2.5-flash`   |
| `LLM_OPENROUTER_PROVIDERS` | **Не используется**                   | Только worker: `Azure`, `Google`, …                            |
| BYOK в UI                  | Base URL + модель + ключ пользователя | То же; `provider` уходит только при `openrouter.ai` в Base URL |
| Из РФ без VPN              | Обычно да                             | Часто нужен VPN или провайдеры вроде Azure/Google              |

#### Модель по умолчанию: `gemini/gemini-2.5-flash` через ProxyAPI

Значения заданы в [`config/settings.py`](config/settings.py) (`LLM_MODEL`, `DEFAULT_LLM_BASE_URL`) и [`.env.example`](.env.example):

```env
LLM_BASE_URL=https://openai.api.proxyapi.ru/v1
LLM_MODEL=gemini/gemini-2.5-flash
```

Почему именно эта связка:

1. **Работает из РФ без VPN** — ProxyAPI доступен с российских хостингов; OpenRouter с 2026 года часто блокируется на edge без VPN.
2. **Покрывает весь граф** — `gemini/gemini-2.5-flash` поддерживает tool calling и `structured_output` (`method="json_schema"`) для узлов `researcher` и `writer`.
3. **BYOK в профиле** — каждый пользователь задаёт свой ключ ProxyAPI (или другого провайдера), Base URL и модель в **Настройках**.

Минимальные BYOK-настройки в веб-интерфейсе:

- Base URL: `https://openai.api.proxyapi.ru/v1`
- Модель: `gemini/gemini-2.5-flash`
- API key: ключ [ProxyAPI](https://proxyapi.ru)

Параметр `provider` (маршрутизация OpenRouter) отправляется **только** при Base URL с `openrouter.ai` — из BYOK пользователя, а не из `LLM_BASE_URL` в `.env` worker.

#### Альтернатива: OpenRouter

Если нужен доступ к каталогу моделей OpenRouter (и есть VPN или хостинг вне РФ), в **Настройках** укажите:

```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4.1-mini
```

Для OpenRouter на worker можно задать `LLM_OPENROUTER_PROVIDERS=Azure` — белый список в `get_llm_extra_body()`.

**OpenRouter из РФ без VPN** (если edge не блокирует): модели Google обычно доступны:

```env
LLM_MODEL=google/gemini-2.5-flash
LLM_OPENROUTER_PROVIDERS=Google,Google AI Studio
```

`LLM_OPENROUTER_PROVIDERS` — переменная окружения **worker**, общая для всех пользователей инстанса. Чтобы разным пользователям одновременно работали модели разных провайдеров, расширьте список: `LLM_OPENROUTER_PROVIDERS=Azure,Google,Google AI Studio`.

#### Рекомендуемые альтернативы (OpenRouter)

Проверено по OpenRouter API (`/models/{id}/endpoints`): у каждой модели на указанных провайдерах есть `tools` и `structured_outputs` (или `response_format`). Поддержка на endpoint может меняться — автопроверка: `python3 -m unittest tests.test_recommended_llm_models`.

| Модель                              | Производитель | Провайдер OpenRouter         | ~Цена in/out  | VPN                        |
| ----------------------------------- | ------------- | ---------------------------- | ------------- | -------------------------- |
| `openai/gpt-4.1-mini`               | OpenAI        | `Azure`                      | $0.40 / $1.60 | Обычно не нужен (Azure)    |
| `openai/gpt-4o-mini`                | OpenAI        | `OpenAI`                     | $0.15 / $0.60 | **Да** (403 из РФ без VPN) |
| `google/gemini-2.5-flash-lite`      | Google        | `Google`, `Google AI Studio` | $0.10 / $0.40 | Обычно не нужен            |
| `deepseek/deepseek-chat-v3.1`       | DeepSeek      | `DeepInfra`                  | $0.21 / $0.80 | Обычно не нужен            |
| `meta-llama/llama-3.3-70b-instruct` | Meta          | `DeepInfra`, `Together`      | $0.10 / $0.32 | Обычно не нужен            |
| `google/gemma-3-12b-it`                  | Google        | `DeepInfra`                  | $0.05 / $0.10 | Обычно не нужен            |

Примеры `.env` для OpenRouter:

```env
# OpenAI через Azure — без VPN из РФ
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4.1-mini
LLM_OPENROUTER_PROVIDERS=Azure
```

```env
# Google — без VPN
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=google/gemini-2.5-flash-lite
LLM_OPENROUTER_PROVIDERS=Google,Google AI Studio
```

```env
# DeepSeek
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-chat-v3.1
LLM_OPENROUTER_PROVIDERS=DeepInfra
```

Проверка связи с LLM: `python3 scripts/test_llm.py`.

---

## Архитектура

Граф LangGraph ([`agents/graph.py`](agents/graph.py)) — схема из кода:

![Схема графа агента](docs/assets/graph.png)

Пунктирные рёбра — условные переходы (`route_entry`, `tool_calls`, `route_after_executor`, critic retry). Сплошные — фиксированные (`writer → critic`).

После `executor` готовность tools проверяется **кодом** ([`planning/tools_readiness.py`](planning/tools_readiness.py)): при успешном `search_route_materials` граф идёт сразу в `writer`, без второго LLM-вызова researcher. При ошибке tool — retry `researcher`.

**API и БД:** `api-node/` (Fastify) вызывает Postgres; фоновые прогоны — `python -m worker` (LangGraph). `executor` пишет `tool_runs`, финальная версия — в `itinerary_versions`. Веб: `web/` (React 19, Ant Design, TanStack Query).

После изменения графа перегенерируйте PNG:

```bash
python3 scripts/render_graph.py
```

| Узел                     | Файл                                               | Роль                                                                                                 |
| ------------------------ | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `researcher`             | `agents/nodes.py`                                  | LLM + tool_calls по `rebuild_scope`                                                                  |
| `executor`               | `agents/nodes.py`                                  | Выполняет tools, пишет строки в `tool_runs`                                                          |
| `writer`                 | `agents/nodes.py`                                  | Structured output → маршруты (`RoutesDraft`), merge; факт о городе — не здесь                        |
| `critic`                 | `agents/critic.py`                                 | Детерминированные проверки; retry: tools → `researcher`, качество программы → `writer`               |
| _(async)_ `city_fact`    | `agents/city_fact.py`, `services/city_fact_job.py` | Wikidata/Nominatim → LLM-polish; патч `lifehacks` + `city_fact_status` в SQLite параллельно с графом |
| _(on-demand)_ `poi_fact` | `agents/poi_fact.py`, `poi_facts`                  | Клик по остановке → LLM-справка по промпту «В городе X есть Y…»; кэш в Postgres                      |

**Инструменты** (`search/tools.py`):

| Инструмент               | Что ищет                                                                     |
| ------------------------ | ---------------------------------------------------------------------------- |
| `search_route_materials` | Пул POI: **city pack** (`poi.sqlite`) если готов; иначе Wikidata + discovery |

Запросы дополняются **`search_context`** из опросника (`search/context.py`). Постфильтрация сниппетов — `config/settings.py` → `SEARCH_FILTERS`.

**Стек:** LangGraph 0.2+, LangChain 0.3, ProxyAPI `gemini/gemini-2.5-flash` (`agents/llm.py`), Pydantic, SQLite, **ddgs** / Tavily, PyYAML (eval).

### Eval (уровни проверки)

| Уровень | Модуль                         | Что проверяет                                       |
| ------- | ------------------------------ | --------------------------------------------------- |
| 1       | `eval/checks/deterministic.py` | JSON-схема `FinalProgram`, `maps_route_url`         |
| 2       | `eval/checks/tools.py`         | Вызовы tools, `live_data`, `results_count`          |
| 3       | `eval/checks/llm_judge.py`     | Опционально: цены со ссылками, город (`--with-llm`) |
| 4       | `eval/checks/regression.py`    | Метрики vs `eval/golden/*.json`                     |

Датасет: `eval/dataset/smoke.yaml`. Запуск: `python3 -m eval --suite smoke`.

---

## Проектирование агента

### Какую задачу решает агент?

По городу, предпочтениям и базовой точке (`route_anchor`) агент **собирает пул POI**, формирует **три маршрута A/B/C** и **факт о городе** (Wikidata → короткий LLM-polish), сохраняет версии в PostgreSQL.

### Кто будет пользоваться агентом?

**Частные путешественники** через [progulyai.ru](https://progulyai.ru): регистрация, BYOK LLM (ProxyAPI/OpenRouter и др.), создание прогулки и пересбор маршрутов.

### С какими внешними системами и данными работает агент?

| Система                                      | Назначение                                                                                                         |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **LLM (ProxyAPI / OpenRouter и др.)**        | Researcher, writer, опционально LLM-judge в eval (`gemini/gemini-2.5-flash` по умолчанию)                          |
| **PostgreSQL** (`DATABASE_URL`)              | Поездки, программы, auth, graph_runs, audit                                                                        |
| **Redis** (`REDIS_URL`)                      | Очередь worker, locks, per-user run quotas                                                                         |
| **Tavily API** (опционально)                 | Веб-поиск с ответом-сводкой                                                                                        |
| **DuckDuckGo** (`ddgs`, ru-ru)               | Веб-поиск по умолчанию                                                                                             |
| **LangFuse** (опционально)                   | Трейсы запусков LangGraph/LLM/tools (self-hosted через Docker)                                                     |
| **LangSmith** (опционально)                  | Трейсы графа (`observability/tracing.py`)                                                                          |
| **Яндекс.Карты (Geocoder + JS API)**         | Геокодинг базовой точки; карта стартовой точки (`ymaps.Map`); маршрут — iframe-виджет + deep link `maps_route_url` |
| **City pack**                                | POI из `poi.sqlite`; каталог `city_packs` в Postgres                                                               |
| **OpenStreetMap** (Nominatim, Geofabrik PBF) | Центр города; выжимки city pack                                                                                    |
| **Wikidata SPARQL**                          | Достопримечательности (P625)                                                                                       |

Маршруты: `search/yandex/materials.py`, контракт — `models/routes.py`; базовая точка — `onboarding/preferences.py` (`route_anchor`). Пул POI: Wikidata Tier 0 + Tier 1 до ~50. LLM ранжирует `poi_id`; `agents/route_postprocess.py` проверяет км, дубли и overlap A/B/C.

### Почему нужен именно агент, а не workflow?

- **Нестабильный ввод**: даты и города в свободной форме, опросник и уточнения в запросе.
- **Многошаговый сбор**: researcher решает, какие tools вызвать; critic и пользователь могут инициировать повтор.
- **Синтез из шума**: LLM отбирает факты из `digest`, группирует по районам.
- **Память и итерации**: Postgres, частичный пересбор (`routes` / `full`), автосохранение программы после critic.

Детерминированный пайплайн «3 HTTP-запроса → шаблон» не покрывает вариативность запросов и качество сниппетов.

### Почему здесь не нужен RAG

В этом проекте RAG **не даёт ключевой пользы**, потому что задача требует **актуальных данных** (события, цены, расписания) и **ссылок на первоисточники**. Поэтому основной подход — web-search tools + структурирование результата:

- Источник знаний — **живой веб‑поиск** (`ddgs` / Tavily) и ссылки в `digest`, а не статичный корпус документов.
- Postgres здесь — **память/версии/профиль**, а не база знаний для retrieval.
- RAG усложнит систему (эмбеддинги, актуализация, качество корпуса), но не решит проблему «актуальность» — всё равно нужен web.
  Если расширять проект дальше, RAG был бы уместен для локальной базы: FAQ по визам/транспорту, чек‑листы, правила пересадок, «best practices» по городу и т.п.

### Сложные и нестандартные ситуации

| Ситуация                            | Обработка                                                                                                                                                                                   |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Пустой или нерелевантный поиск**  | Фильтр по `SEARCH_FILTERS` + fallback demo-POI; warning в `data_warnings` (API + баннер в UI)                                                                                               |
| **Ошибка поиска / сети**            | `ToolMessage` с ошибкой; `route_after_executor` → retry `researcher`; `tool_runs` с `live_data=false`                                                                                       |
| **Prompt-injection во вводе**       | `input_validation.sanitize_and_validate`                                                                                                                                                    |
| **Галлюцинации мест**               | Маршруты — только `poi_id` из пула materials                                                                                                                                                |
| **Critic не прошёл**                | До 2 повторов: проблемы tools/POI → `researcher`, проблемы маршрутов → `writer`; факт о городе critic не блокирует, пока `city_fact_status=pending`                                         |
| **Повторный запуск**                | `user_profile` + `trip_preferences` из SQLite                                                                                                                                               |
| **Город в каталоге, pack не готов** | Wikidata не подмешивается; worker ставит `prepare_city_pack`; пока пустой пул — demo-POI + предупреждение                                                                                   |
| **Демо-точки вместо POI**           | Wikidata SPARQL не ответила (таймаут/сеть) — до 3 повторов; центр города — Nominatim (для Москвы — `place/city`, не administrative). Проверка: `python3 scripts/test_yandex_maps.py Москва` |
| **Одинаковые маршруты A/B/C**       | `finalize_route_program` разводит пары A–B, B–C, A–C по overlap POI; critic отклоняет совпадения и один `maps_route_url` → retry `writer`                                                   |
| **LLM-маршрут не прошёл валидацию** | Неверный `poi_id`, &lt; min км или overlap пар &gt; порога — подставляется алгоритм A/B/C (`build_hybrid_route_program`)                                                                    |
| **Кольцевой маршрут**               | При `loop_route: true` от LLM или эвристике (набережная, мосты, компактный центр) пост-процессор замыкает `maps_route_url` в кольцо, если возврат к старту не превышает лимит км            |
| **Дизлайк остановки и пересборка**  | 👎 на `route_stops` не сбрасывается после rebuild; `banned_poi_ids` в snapshot + `enforce_route_poi_policy` исключают POI даже при готовых `maps_route_url`                                 |

### Как понять, что агент работает хорошо?

| Критерий                           | Приемлемый результат                                                                                                                                                                                                           |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Полнота программы**              | 3 варианта маршрута A/B/C; факт о городе 280–1400 символов с датами и местами; справка по POI 300–2200 символов (LLM, on-demand)                                                                                               |
| **Опора на поиск**                 | Маршруты A/B/C: сложность по **протяжённости** (A ~2–3.5 км, B ~4–5.5, C ~6–8.5), до 8 плотных leisure-точек; без повторов названий; `maps_route_url` по координатам (иногда кольцевой); POI только из Wikidata/discovery-пула |
| **Надёжность и воспроизводимость** | `python3 -m unittest discover -s tests -v` и `python3 -m eval --suite smoke` проходят                                                                                                                                          |

---

## Observability (LangFuse + LangSmith)

### LangFuse (self-hosted)

1. Поднять LangFuse локально:

```bash
cd docker/langfuse
cp .env.example .env
docker compose --env-file .env -f docker-compose.yml up -d
```

2. Взять ключи проекта в UI LangFuse (`http://localhost:3000`) и прописать в `.env` проекта:

- `LANGFUSE_ENABLED=true`
- `LANGFUSE_HOST=http://localhost:3000` (или `LANGFUSE_HOST_DOCKER=...` при запуске в Docker)
- `LANGFUSE_PUBLIC_KEY=...`
- `LANGFUSE_SECRET_KEY=...`

3. Запустите api-node (`cd api-node && npm run dev`) или создайте поездку через веб — трейсинг пойдёт через LangChain callbacks.

### LangSmith (опционально, параллельно)

LangSmith можно включить одновременно с LangFuse:

- `LANGCHAIN_TRACING_V2=true`
- `LANGCHAIN_API_KEY=...`
- `LANGCHAIN_PROJECT=tourist-assistant`

---

## Метрики

- **Success rate**: `python3 -m eval --suite smoke` (10 кейсов в `eval/dataset/smoke.yaml`)
- **Latency p95 / cost per run**: после нескольких прогонов через веб/API:

```bash
python3 -m scripts.metrics_report --limit 50
python3 -m scripts.metrics_report --trip-id 12
```

В `agent_runs` сохраняются `duration_ms`, tokens/cost и **`node_timings`** (JSON: узлы `researcher` / `executor` / `writer` / `critic` + tools).

Примечание: стоимость/токены пишутся через `get_openai_callback()` и могут быть пустыми для не-OpenAI провайдеров.

### Статистика пользователей (консоль, без админки)

**Одна команда** — локально и на VPS (сама выбирает prod Docker / dev Docker / `.venv`):

```bash
./stats.sh summary
./stats.sh registrations --days 30
./stats.sh logins --days 30
./stats.sh online --minutes 5
./stats.sh activity --limit 20
./stats.sh user --email user@example.com
```

- **VPS:** `cd /opt/tourist-assistant && ./stats.sh summary` (скрипт деплоится как `/opt/tourist-assistant/stats.sh`)
- **Из репозитория:** `bash scripts/stats.sh summary`

После миграции (`alembic upgrade head`) и деплоя api-node с audit на auth.

Источники данных:

- **Регистрации** — `users.created_at`; события `user.register` в `audit_events` (email/Google)
- **Логины** — `audit_events` (`user.login` при register/login/OAuth)
- **«Онлайн»** — `users.last_seen_at` (обновляется при авторизованных API-запросах, debounce 1 мин)
- **Действия** — `audit_events` (`trip.create`, `graph_run.start`, …) + агрегаты `trips` / `graph_runs` / `usage_events`

---

## Структура репозитория

```
tourist-assistant/
├── api-node/               # Node.js REST API (Fastify, Postgres + Redis)
├── Dockerfile.api-node     # Docker: Node API + Python repair_program_cli
├── scripts/repair_program_cli.py  # repair_program_routes для GET program
├── scripts/admin_stats.py         # логика статистики (Postgres)
├── scripts/stats.sh               # единая команда: ./stats.sh summary
├── auth/                   # BYOK crypto, require_user_llm_config (worker)
├── docs/openapi.json       # OpenAPI 3 (npm run export:openapi)
├── services/               # TripService, RunManager, json_job_queue
├── worker/                 # Python worker (JSON Redis queue, python -m worker)
├── web/                    # Vite + React 19, Ant Design, TanStack Query
├── alembic/                # Миграции Postgres (Alembic)
├── db/
│   ├── models/             # SQLAlchemy models (PG)
│   ├── session.py          # DATABASE_URL engine
│   ├── connection.py       # init_db → Alembic
│   ├── postgres/repository.py
│   ├── postgres/users.py
│   ├── repository.py       # facade → Postgres
│   ├── users.py            # auth/BYOK facade
├── config/settings.py      # .env, SEARCH_FILTERS, лимиты LLM/поиска
├── models/
│   ├── schemas.py          # FinalProgram, ProgramDraft, RouteMaterialsInput
│   ├── routes.py           # RouteMaterials, TripRouteCase, RouteProgram
│   └── state.py            # AgentState
├── input_validation.py     # sanitize_and_validate
├── planning/dates.py       # parse_trip_dates
├── search/
│   ├── web.py              # Tavily / ddgs, digest
│   ├── tools.py            # @tool search_route_materials
│   ├── osm/                # Nominatim, city pack POI
│   ├── wikidata/           # SPARQL достопримечательностей, city_description (факт)
│   ├── yandex/             # materials, maps_route_url
│   ├── context.py          # ContextVar: prefs + route_materials (worker-safe)
│   └── tool_logging.py     # разбор payload для tool_runs
├── agents/
│   ├── llm.py              # ChatOpenAI, llm_with_tools, llm_final
│   ├── nodes.py            # researcher, executor, writer, critic
│   ├── graph.py            # сборка LangGraph, app
│   ├── critic.py
│   ├── city_fact.py        # Wikidata → LLM-polish, validation
│   └── print_program.py
├── planning/rebuild.py       # rebuild_scope, merge_program
├── program/parse_items.py  # разбор markdown-секций на пункты
├── program/route_feedback.py  # лайкнутые маршруты при partial rebuild
├── program/route_stops.py     # голосование за POI-остановки
├── db/                     # schema.sql, repository, bootstrap user id=1
├── onboarding/             # TripPreferences
├── observability/          # LangFuse tracing
├── eval/                   # python3 -m eval --suite smoke
├── scripts/render_graph.py # PNG графа → docs/assets/graph.png
├── config/city_packs.yaml      # каталог городов (8 × Поволжье)
├── config/federal_districts.yaml
├── scripts/fo_ensure.sh        # Geofabrik FO PBF
├── scripts/city_pack_prepare.sh
├── scripts/city_pack_batch.sh
├── db/postgres/city_packs.py   # статусы pack в Postgres
├── docs/assets/graph.png
├── tests/
├── data/                   # локальные артефакты (в .gitignore)
├── requirements.txt
├── Dockerfile              # Python worker image
├── .github/workflows/      # CI (PR) и Deploy (main → GHCR + VPS)
├── deploy/                 # docker-compose.prod.yml, env.example для VPS
├── docker-compose.yml      # лок/dev: postgres, redis, api-node, worker, web
├── .env.example
└── README.md
```

---

## Разработка

- Перед коммитом синхронизируйте **README** с кодом — см. [`.cursor/rules/readme-sync.mdc`](.cursor/rules/readme-sync.mdc) (правило для агента Cursor при коммите, не pre-commit hook).
- При правках **`agents/graph.py`** выполните `python3 scripts/render_graph.py` и закоммитьте обновлённый `docs/assets/graph.png`.
- Зависимости: `pip install -r requirements.txt`; при новых пакетах обновляйте `requirements.txt`.
- Коммиты: [Conventional Commits](.cursor/rules/conventional-commits.mdc), subject ≤ 20 символов.
- Не коммитьте `.env` с секретами.

## Лицензия

Уточните у владельца репозитория.
