# Туристический ассистент (LangGraph)

Агент составляет **маршруты по городу**: три альтернативных варианта A/B/C на основе пула POI из **Wikidata/OSM**, с deep link в Яндекс.Карты и блоком **«О городе»** (факт из Wikidata/Nominatim, 2 предложения на русском). Центральная функция продукта — маршруты и базовая точка старта (`route_anchor`). Поездки, предпочтения и версии программы хранятся в **PostgreSQL**.

## Статус и планы

Приложение находится **в стадии активной разработки**. Текущая версия — **routes-first MVP**: агент собирает три маршрута; **факт о городе** подгружается **параллельно** (маршруты показываются сразу, блок «О городе» — по готовности). **Веб-интерфейс и REST API** позволяют создавать поездки и пересобирать маршруты. Консольный CLI снят.

**Ближайшие планы:**

| Направление | Что планируется |
|-------------|-----------------|
| **Маршруты** | Базовая точка (отель/адрес) на карте Яндекс.Карт; улучшение пешеходных маршрутов по выгрузкам [Geofabrik](https://download.geofabrik.de/) |
| **SaaS** | Многопользовательский режим: регистрация, личный кабинет, изоляция поездок по аккаунту (Postgres + Node API) |

## Быстрый старт

### Требования

- Python **3.10+** (работает на 3.9+)
- Ключ **OpenRouter** ([openrouter.ai/keys](https://openrouter.ai/keys))

### Быстрый старт (Docker)

```bash
git clone <url-репозитория>
cd tourist-assistant

test -f .env || cp .env.example .env
# DATABASE_URL, REDIS_URL, JWT_SECRET, SETTINGS_ENCRYPTION_KEY — обязательны

docker compose up -d --build
```

UI: [http://localhost:5173](http://localhost:5173), API health: [http://localhost:8001/api/health](http://localhost:8001/api/health).

### Локальная разработка (API + React)

Требования: Python 3.10+, Node.js 20+, Postgres и Redis. В `.env`: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `SETTINGS_ENCRYPTION_KEY` (см. `.env.example`). Ключ OpenRouter каждый пользователь задаёт в **Настройках** (BYOK). Для `python -m eval --with-llm` нужен `LLM_API_KEY` в `.env`.

**Инфра (терминал 0):**

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

Откройте [http://localhost:5173](http://localhost:5173). Vite проксирует `/api` на `http://127.0.0.1:8001` (api-node). На главной (`/`) — лендинг; для работы нужны **регистрация** (`/register`) или **вход** (`/login`, в т.ч. Google OAuth), затем в **Настройках** — ключ [OpenRouter](https://openrouter.ai/keys). Список поездок — `/trips`.

**Проверка с телефона (PWA):**

1. Mac и телефон в одной Wi‑Fi; запустите API и `npm run dev` (как выше).
2. В выводе Vite найдите строку **Phone / PWA dev URL** (`https://192.168.x.x:5173`) или узнайте IP: `ipconfig getifaddr en0`.
3. Откройте **HTTPS**-адрес **в Safari/Chrome** (не через иконку «На экран Домой», если раньше добавляли `localhost`). При первом заходе браузер попросит доверять dev-сертификату — без HTTPS геолокация на карте маршрута не работает.
4. **macOS:** если не открывается — **Системные настройки → Сеть → Брандмауэр → Параметры** → для **node** выберите «Разрешить входящие подключения».
5. **Чёрный экран:** перезапустите `npm run dev` (Vite прописывает HMR на IP Mac). На iPhone: Настройки → Safari → «Дополнения» → «Данные веб-сайтов» → удалите сайт `192.168.x.x`. Не используйте гостевую Wi‑Fi (изоляция клиентов).
6. Установка на главный экран: Android — «Установить приложение»; iPhone — «Поделиться» → «На экран Домой» (после того как сайт открылся в Safari по IP).
7. **Геолокация на карте маршрута:** кнопка-мишень на встроенной карте; разовое определение позиции (нужен `VITE_YANDEX_MAPS_API_KEY` в `web/.env`).

Для стабильного PWA-теста без dev-сервера: `cd web && npm run build && npm run preview -- --host`.

Без открытия портов: `cloudflared tunnel --url http://localhost:5173`. Через Docker: `docker compose up` → `http://<IP-Mac>:5173`.

**API:** Node.js Fastify на порту **8001** (`api-node/`).

**Swagger (живой, из кода):**

- Swagger UI: [http://localhost:8001/docs](http://localhost:8001/docs)
- JSON: [http://localhost:8001/docs/json](http://localhost:8001/docs/json)

Схема в репозитории (`docs/openapi.json`) генерируется из тех же маршрутов:

```bash
python3 scripts/export_openapi.py
# или: cd api-node && npm run export:openapi
```

Pre-commit hook (`./scripts/install_git_hooks.sh`) обновляет `docs/openapi.json` автоматически.

**Базовая точка маршрута:** отель или адрес проживания задаётся в мастере новой поездки или в карточке поездки (аккордеон «Базовая точка маршрута», по умолчанию свёрнут; скрывается на время сборки/пересборки). API: `PUT /api/trips/{id}/preferences` (`route_anchor`), геокодинг `POST /api/trips/geocode` и `POST /api/trips/{id}/geocode`, обратный геокодинг `POST /api/trips/reverse-geocode` и `POST /api/trips/{id}/reverse-geocode`, центр города `GET /api/trips/{id}/city-center`. На фронте — JavaScript API Яндекс.Карт (`VITE_YANDEX_MAPS_API_KEY` в `web/.env`); на бэкенде — `YANDEX_MAPS_API_KEY`. После изменения точки пересбор **только вручную** — «Пересобрать» с областью `routes`. На мобильной вкладке «Маршруты» — переключатель A/B/C (один вариант на экран); на десктопе — три карточки списком.

Один раз установить автообновление схемы перед коммитом:

```bash
./scripts/install_git_hooks.sh
```

| Экран | Действие |
|-------|----------|
| **Вход / регистрация** | Email+пароль или Google; JWT в `localStorage` |
| **Настройки** | BYOK: OpenRouter API key (шифруется в Postgres) |
| **Список поездок** | Только поездки текущего пользователя |
| **Новая поездка** | Wizard: поездка → запуск → фоновая сборка (polling 1–2 мин) |
| **Карточка поездки** | Единая страница маршрутов (A/B/C) с **встроенной картой** + базовая точка; внизу **«О городе»** (skeleton, пока `city_fact_status=pending`); пересбор маршрутов одной кнопкой |

Docker (веб + API): см. [Запуск в Docker](#запуск-в-docker-docker-compose).

**Оценки пунктов (👍/👎):** для **вариантов маршрута и остановок** (блок «О городе» без голосования). Веб: клик → `PUT /api/trips/{id}/program/feedback`. Хранение: `program_item_feedback` (Postgres). **👎 на остановку** — жёсткий запрет `poi_id` при пересборке (дизлайк сохраняется между прогонами); похожие места (тот же мотив/имя, напр. собор и памятник Ушакова) тоже исключаются. **👎 на вариант маршрута** — мягкая подсказка LLM + бан остановок этого варианта.

### Запуск в Docker (Docker Compose)

Требования: [Docker](https://docs.docker.com/get-docker/) и Docker Compose v2.

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

| Подход | Плюсы | Минусы |
|--------|-------|--------|
| **Текущий: гибридный образ** (`Dockerfile.api-node`) | Полный parity с Python; один контейнер | Больший образ; rebuild при изменении Python repair |
| **Чистый Node-образ + HTTP к worker** | Маленький api-node; repair всегда свежий в worker | Нужен внутренний endpoint на worker; сеть между сервисами |
| **Чистый Node + volume mount Python** (только dev) | Без rebuild в dev | Не для prod; хрупко |
| **Порт repair на TypeScript** | Один runtime в api-node | Дублирование ~1000 строк `route_postprocess` |
| **Отдельный микросервис `repair`** | Изоляция | Ещё один деплой |

Для prod сейчас оптимален гибридный образ; при частых правках repair удобнее вынести HTTP-вызов на worker (тот же код, без копии в api-node).

### Тесты и eval (без полного прогона агента)

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

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `LLM_API_KEY` | Нет* | Для `python -m eval --with-llm` и dev-скриптов; веб-API использует BYOK в профиле |
| `JWT_SECRET` | Да** | Секрет подписи JWT (api-node) |
| `SETTINGS_ENCRYPTION_KEY` | Да** | Fernet-ключ шифрования BYOK в БД (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `JWT_ACCESS_TTL_MINUTES` | Нет | Срок жизни access token (по умолчанию 60) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Нет | Google OAuth (опционально) |
| `GOOGLE_REDIRECT_URI` | Нет | Callback OAuth, по умолчанию `http://localhost:8001/api/auth/google/callback` |
| `CORS_ORIGINS` | Нет | Доп. origins через запятую для прод-домена |
| `LLM_BASE_URL` | Нет | OpenAI-compatible endpoint, по умолчанию `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | Нет | Slug модели на OpenRouter. По умолчанию `openai/gpt-4.1-mini` (см. [Модели LLM](#модели-llm)) |
| `LLM_OPENROUTER_PROVIDERS` | Нет | Белый список провайдеров (порядок = приоритет). По умолчанию: `Azure` |
| `DATABASE_URL` | Да** | PostgreSQL (обязателен для API и worker) |
| `REDIS_URL` | Да** | Redis: JSON worker queue, locks, лимиты прогонов |
| `LANGCHAIN_TRACING_V2` | Нет | `true` — трейсы в [LangSmith](https://smith.langchain.com) |
| `LANGCHAIN_API_KEY` | Нет | Ключ LangSmith |
| `LANGCHAIN_PROJECT` | Нет | Имя проекта (по умолчанию `tourist-assistant`) |
| `LANGSMITH_ENDPOINT` | Нет | Кастомный endpoint LangSmith (опционально) |
| `LANGFUSE_ENABLED` | Нет | `true` — включить трейсы в LangFuse (self-hosted) |
| `LANGFUSE_HOST` | Нет | LangFuse, например `http://localhost:3000` |
| `LANGFUSE_HOST_DOCKER` | Нет | LangFuse для Docker, например `http://host.docker.internal:3000` |
| `LANGFUSE_PUBLIC_KEY` | Нет | Public key проекта LangFuse |
| `LANGFUSE_SECRET_KEY` | Нет | Secret key проекта LangFuse |

**Дополнительно** (дефолты в коде, в `.env.example` нет): `TAVILY_API_KEY` (иначе `ddgs`, ru-ru); `VITE_YANDEX_MAPS_API_KEY` (`web/.env`, карта и геолокация); `VITE_DEV_HTTPS` (`web/.env`, HTTPS dev для геолокации с телефона, по умолчанию вкл. при LAN IP); `POI_USE_WIKIDATA`, `POI_USE_DISCOVERY`, `POI_USE_OVERPASS`; `OVERPASS_URL`, `OVERPASS_URLS`, `OVERPASS_TIMEOUT`; `NOMINATIM_URL`, `NOMINATIM_USER_AGENT`; `YANDEX_MAPS_API_KEY` (HTTP Geocoder на бэкенде).

### Модели LLM

#### Модель по умолчанию: `openai/gpt-4.1-mini`

Значение задано в [`config/settings.py`](config/settings.py) (`LLM_MODEL`) и [`.env.example`](.env.example).

Почему именно она:

1. **Работает из РФ без VPN** — на OpenRouter у `openai/gpt-4.1-mini` есть endpoint **Azure** с `tools` и `structured_outputs` (в отличие от `openai/gpt-4o-mini`, где tools есть только у провайдера OpenAI → 403 из РФ).
2. **Покрывает весь граф** — planner (tools) и writer (structured output) на одной модели.
3. **Баланс цена/качество** — ~$0.40 / $1.60 за 1M токенов (in/out), дешевле флагманов `gpt-4.1` / `gpt-4o`.
4. **Провайдер по умолчанию** — `LLM_OPENROUTER_PROVIDERS=Azure` (белый список в `get_llm_extra_body()`).

Минимальный `.env` без VPN:

```env
LLM_MODEL=openai/gpt-4.1-mini
LLM_OPENROUTER_PROVIDERS=Azure
```

#### Рекомендуемые альтернативы (5 моделей)

Проверено по OpenRouter API (март 2026): у каждой модели на указанных провайдерах есть `tools` и `structured_outputs`. Константа — `RECOMMENDED_ALTERNATIVE_LLM_MODELS` в [`config/settings.py`](config/settings.py); автопроверка — `python3 -m unittest tests.test_recommended_llm_models`.

| Модель | Производитель | Провайдер OpenRouter | ~Цена in/out | VPN |
|--------|---------------|----------------------|--------------|-----|
| `openai/gpt-4o-mini` | OpenAI | `OpenAI` | $0.15 / $0.60 | **Да** (403 из РФ без VPN) |
| `google/gemini-2.5-flash-lite` | Google | `Google`, `Google AI Studio` | $0.10 / $0.40 | Обычно не нужен |
| `deepseek/deepseek-chat-v3.1` | DeepSeek | `DeepInfra` | $0.21 / $0.80 | Обычно не нужен |
| `meta-llama/llama-3.3-70b-instruct` | Meta | `DeepInfra`, `Together` | $0.10 / $0.32 | Обычно не нужен |
| `mistralai/mistral-nemo` | Mistral | `Mistral` | $0.02 / $0.15 | Обычно не нужен |

Примеры `.env`:

```env
# OpenAI — только с VPN из РФ
LLM_MODEL=openai/gpt-4o-mini
LLM_OPENROUTER_PROVIDERS=OpenAI
```

```env
# Google — без VPN
LLM_MODEL=google/gemini-2.5-flash-lite
LLM_OPENROUTER_PROVIDERS=Google,Google AI Studio
```

```env
# DeepSeek
LLM_MODEL=deepseek/deepseek-chat-v3.1
LLM_OPENROUTER_PROVIDERS=DeepInfra
```

Проверка связи с OpenRouter: `python3 scripts/test_llm.py`.

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

| Узел | Файл | Роль |
|------|------|------|
| `researcher` | `agents/nodes.py` | LLM + tool_calls по `rebuild_scope` |
| `executor` | `agents/nodes.py` | Выполняет tools, пишет строки в `tool_runs` |
| `writer` | `agents/nodes.py` | Structured output → маршруты (`RoutesDraft`), merge; факт о городе — не здесь |
| `critic` | `agents/critic.py` | Детерминированные проверки; retry: tools → `researcher`, качество программы → `writer` |
| *(async)* `city_fact` | `agents/city_fact.py`, `services/city_fact_job.py` | Wikidata/Nominatim → LLM-polish; патч `lifehacks` + `city_fact_status` в SQLite параллельно с графом |

**Инструменты** (`search/tools.py`):

| Инструмент | Что ищет |
|------------|----------|
| `search_route_materials` | Полный пул POI (до ~50): Wikidata — все Tier 0, затем Tier 1 по score; набережные по SPARQL; discovery; Overpass опционально (`POI_USE_OVERPASS=true`) |

Запросы дополняются **`search_context`** из опросника (`search/context.py`). Постфильтрация сниппетов — `config/settings.py` → `SEARCH_FILTERS`.

**Стек:** LangGraph 0.2+, LangChain 0.3, OpenRouter `openai/gpt-4.1-mini` / Azure (`agents/llm.py`), Pydantic, SQLite, **ddgs** / Tavily, PyYAML (eval).

### Eval (уровни проверки)

| Уровень | Модуль | Что проверяет |
|---------|--------|----------------|
| 1 | `eval/checks/deterministic.py` | JSON-схема `FinalProgram`, `maps_route_url` в маршрутах |
| 2 | `eval/checks/tools.py` | Вызовы tools, `live_data`, `results_count` |
| 3 | `eval/checks/llm_judge.py` | Опционально: цены со ссылками, город (`--with-llm`) |
| 4 | `eval/checks/regression.py` | Метрики vs `eval/golden/*.json` |

Датасет: `eval/dataset/smoke.yaml`. Запуск: `python3 -m eval --suite smoke`.

---

## Проектирование агента

### Какую задачу решает агент?

По городу, предпочтениям и базовой точке (`route_anchor`) агент **собирает пул POI**, формирует **три маршрута A/B/C** и **факт о городе** (Wikidata → короткий LLM-polish), сохраняет версии в PostgreSQL.

### Кто будет пользоваться агентом?

**Частные путешественники** через веб-приложение: регистрация, BYOK OpenRouter, создание поездки и пересбор маршрутов.

### С какими внешними системами и данными работает агент?

| Система | Назначение |
|---------|------------|
| **OpenRouter** | Researcher, writer, опционально LLM-judge в eval (`openai/gpt-4.1-mini` через Azure) |
| **PostgreSQL** (`DATABASE_URL`) | Поездки, программы, auth, graph_runs, audit |
| **Redis** (`REDIS_URL`) | Очередь worker, locks, per-user run quotas |
| **Tavily API** (опционально) | Веб-поиск с ответом-сводкой |
| **DuckDuckGo** (`ddgs`, ru-ru) | Веб-поиск по умолчанию |
| **LangFuse** (опционально) | Трейсы запусков LangGraph/LLM/tools (self-hosted через Docker) |
| **LangSmith** (опционально) | Трейсы графа (`observability/tracing.py`) |
| **Яндекс.Карты (Geocoder + JS API)** | Геокодинг базовой точки; deep link `maps_route_url` |
| **OpenStreetMap** (Overpass + Nominatim) | POI с координатами |
| **Wikidata SPARQL** | Достопримечательности (P625) |

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

| Ситуация | Обработка |
|----------|-----------|
| **Пустой или нерелевантный поиск** | Фильтр по `SEARCH_FILTERS` + fallback demo-POI; warning в `data_warnings` (API + баннер в UI) |
| **Ошибка поиска / сети** | `ToolMessage` с ошибкой; `route_after_executor` → retry `researcher`; `tool_runs` с `live_data=false` |
| **Prompt-injection во вводе** | `input_validation.sanitize_and_validate` |
| **Галлюцинации мест** | Маршруты — только `poi_id` из пула materials |
| **Critic не прошёл** | До 2 повторов: проблемы tools/POI → `researcher`, проблемы маршрутов → `writer`; факт о городе critic не блокирует, пока `city_fact_status=pending` |
| **Повторный запуск** | `user_profile` + `trip_preferences` из SQLite |
| **Демо-точки вместо POI** | Wikidata SPARQL не ответила (таймаут/сеть) — до 3 повторов; центр города — Nominatim (для Москвы — `place/city`, не administrative). Проверка: `python3 scripts/test_yandex_maps.py Москва` |
| **Одинаковые маршруты A/B/C** | `finalize_route_program` разводит пары A–B, B–C, A–C по overlap POI; critic отклоняет совпадения и один `maps_route_url` → retry `writer` |
| **LLM-маршрут не прошёл валидацию** | Неверный `poi_id`, &lt; min км или overlap пар &gt; порога — подставляется алгоритм A/B/C (`build_hybrid_route_program`) |
| **Кольцевой маршрут** | При `loop_route: true` от LLM или эвристике (набережная, мосты, компактный центр) пост-процессор замыкает `maps_route_url` в кольцо, если возврат к старту не превышает лимит км |
| **Дизлайк остановки и пересборка** | 👎 на `route_stops` не сбрасывается после rebuild; `banned_poi_ids` в snapshot + `enforce_route_poi_policy` исключают POI даже при готовых `maps_route_url` |

### Как понять, что агент работает хорошо?

| Критерий | Приемлемый результат |
|----------|----------------------|
| **Полнота программы** | 3 варианта маршрута A/B/C; факт о городе 80–520 символов, туристический угол (не админ-справка) |
| **Опора на поиск** | Маршруты A/B/C: сложность по **протяжённости** (A ~2–3.5 км, B ~4–5.5, C ~6–8.5), до 8 плотных leisure-точек; без повторов названий; `maps_route_url` по координатам (иногда кольцевой); POI только из Wikidata/discovery-пула |
| **Надёжность и воспроизводимость** | `python3 -m unittest discover -s tests -v` и `python3 -m eval --suite smoke` проходят |

---

## Observability (LangFuse + LangSmith)

### LangFuse (self-hosted)

1) Поднять LangFuse локально:

```bash
cd docker/langfuse
cp .env.example .env
docker compose --env-file .env -f docker-compose.yml up -d
```

2) Взять ключи проекта в UI LangFuse (`http://localhost:3000`) и прописать в `.env` проекта:

- `LANGFUSE_ENABLED=true`
- `LANGFUSE_HOST=http://localhost:3000` (или `LANGFUSE_HOST_DOCKER=...` при запуске в Docker)
- `LANGFUSE_PUBLIC_KEY=...`
- `LANGFUSE_SECRET_KEY=...`

3) Запустите api-node (`cd api-node && npm run dev`) или создайте поездку через веб — трейсинг пойдёт через LangChain callbacks.

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

---

## Структура репозитория

```
tourist-assistant/
├── api-node/               # Node.js REST API (Fastify, Postgres + Redis)
├── Dockerfile.api-node     # Docker: Node API + Python repair_program_cli
├── scripts/repair_program_cli.py  # repair_program_routes для GET program
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
│   ├── osm/                # Nominatim, Overpass
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
├── docs/assets/graph.png
├── tests/
├── data/                   # локальные артефакты (в .gitignore)
├── requirements.txt
├── Dockerfile              # Python worker image
├── docker-compose.yml      # postgres, redis, api-node, worker, web
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
