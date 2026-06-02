# Туристический ассистент (LangGraph)

Агент составляет **культурную программу поездки** по городу и датам: билеты туда-обратно (самолёт, поезд, автобус), музеи и мероприятия, рестораны в пешей доступности от достопримечательностей, городской транспорт и лайфхаки. Данные берутся из **живого веб-поиска** (Tavily или DuckDuckGo `ddgs`), не из заглушек. Перед планированием — **опросник** (7 вопросов при первом запуске); поездки, предпочтения и версии программы хранятся в **SQLite**.

## Быстрый старт

### Требования

- Python **3.10+** (работает на 3.9+)
- Ключ **OpenAI API** (через [ProxyAPI](https://proxyapi.ru) или напрямую)

### Установка и запуск

```bash
git clone <url-репозитория>
cd tourist-assistant

python3 -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Отредактируйте .env: OPENAI_API_KEY=sk-...

python3 main.py
```

Пример ввода в режиме «Новая поездка»:

- Город: `Санкт-Петербург`
- Даты: `1-4 августа 2026`
- Вылет: `Москва` (Enter — по умолчанию)
- Запрос: `Составь культурную программу, рестораны от 4.7`

### Меню CLI

| Режим | Действие |
|-------|----------|
| **Новая поездка** | Город, даты, вылет, запрос → опросник (см. ниже) → веб-поиск → программа → **утверждение Y/n** |
| **Продолжить** | Выбор поездки по `id` → что пересобрать (всё или раздел) → снова граф и HITL |
| **Показать подробности** | Программа и предпочтения из БД **без** нового поиска и LLM |

**Опросник предпочтений**

- **Первый запуск** — полные 7 вопросов (темп, бюджет, интересы, кухня, рейтинг ресторанов, транспорт, состав группы).
- **Повторный запуск** — по умолчанию берутся сохранённые предпочтения (`user_profile` в SQLite); опрос только если ответить «да» на «Пройти опрос заново?».

**Частичный пересбор** (режим «Продолжить»): `full`, `tickets`, `events`, `dining`, `transport`, `lifehacks` (лайфхаки — без нового веб-поиска).

После сборки программы: разделы **Билеты**, **Мероприятия**, **Питание**, **Транспорт**, **Лайфхаки** (обычно 1–2 минуты).

### Тесты и eval (без полного прогона агента)

Запускайте **по одной строке** (не копируйте `#` в конце строки — shell воспримет это как аргумент).

```bash
python3 -m unittest discover -s tests -v
```

```bash
python3 -m eval --suite smoke
```

С LLM-judge (нужен `OPENAI_API_KEY`):

```bash
python3 -m eval --suite smoke --with-llm
```

Eval проверяет **fixtures** в `eval/fixtures/` (схема программы, tool_runs, regression к `eval/golden/`), а не живой интернет.

### Benchmark (10+ кейсов)

Минимальный benchmark для диплома лежит в `eval/dataset/smoke.yaml` (**10 кейсов**). Каждый кейс содержит:

- **input**: `city`, `dates`, `origin_city`, `user_query`
- **expected output**: ожидаемые tools, секции и детерминированные маркеры (ссылки/подписи)

Запуск и success rate:

```bash
python3 -m eval --suite smoke
```

### Переменные окружения

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `OPENAI_API_KEY` | Да* | Ключ ProxyAPI для зарубежных моделей (*не нужен для `unittest` и `eval --suite smoke` без `--with-llm`) |
| `YANDEX_API_KEY` | Нет* | Ключ Yandex Cloud для `LLM_MODEL_RU` (*нужен для поездок по РФ при роутинге `ru`) |
| `YANDEX_FOLDER_ID` | Нет | ID каталога YC; если не задан — берётся из `gpt://<folder_id>/...` в `LLM_MODEL_RU` |
| `PROXY_BASE_URL` | Нет | Fallback endpoint, по умолчанию `https://openai.api.proxyapi.ru/v1` |
| `LLM_REGION` | Нет | Роутинг модели: `auto`/`ru`/`intl` (по умолчанию `auto`) |
| `LLM_MODEL_RU` | Нет | Модель Yandex (например `gpt://<folder>/aliceai-llm/latest`) |
| `LLM_MODEL_INTL` | Нет | Модель ProxyAPI (например `gpt-4o-mini`) |
| `PROXY_BASE_URL_RU` | Нет | Yandex: `https://llm.api.cloud.yandex.net/v1` (не proxyapi.ru) |
| `PROXY_BASE_URL_INTL` | Нет | ProxyAPI: `https://openai.api.proxyapi.ru/v1` |
| `TAVILY_API_KEY` | Нет | Точнее веб-поиск; без ключа — DuckDuckGo (`ddgs`, регион `ru-ru`) |
| `DATABASE_PATH` | Нет | SQLite, по умолчанию `data/trips.db` |
| `LANGCHAIN_TRACING_V2` | Нет | `true` — трейсы в [LangSmith](https://smith.langchain.com) |
| `LANGCHAIN_API_KEY` | Нет | Ключ LangSmith |
| `LANGCHAIN_PROJECT` | Нет | Имя проекта (по умолчанию `tourist-assistant`) |
| `LANGFUSE_ENABLED` | Нет | `true` — включить трейсы в LangFuse (self-hosted) |
| `LANGFUSE_HOST` | Нет | URL LangFuse, например `http://localhost:3000` |
| `LANGFUSE_PUBLIC_KEY` | Нет | Public key проекта LangFuse |
| `LANGFUSE_SECRET_KEY` | Нет | Secret key проекта LangFuse |

Шаблон: [`.env.example`](.env.example).

---

## Архитектура

Граф LangGraph ([`agents/graph.py`](agents/graph.py)) — схема из кода (как в LangGraph Studio):

![Схема графа агента](docs/assets/graph.png)

Пунктирные рёбра — условные переходы (`lifehacks`, `tool_calls`, critic retry, HITL). Сплошные — фиксированные (`executor → researcher`, `writer → critic`).

**CLI и БД:** `cli/app.py` вызывает `app.invoke`; `executor` пишет `tool_runs`, финальная версия — в `itinerary_versions` (SQLite).

После изменения графа перегенерируйте PNG:

```bash
python3 scripts/render_graph.py
```

| Узел | Файл | Роль |
|------|------|------|
| `researcher` | `agents/nodes.py` | LLM + tool_calls по `rebuild_scope` |
| `executor` | `agents/nodes.py` | Выполняет tools, пишет строки в `tool_runs` |
| `writer` | `agents/nodes.py` | Structured output → `FinalProgram`, merge с прошлой версией |
| `critic` | `agents/critic.py` | Детерминированные проверки перед показом пользователю |
| `human_review` | `agents/human_review.py` | Утвердить программу? Y/n; при отказе — пересбор или черновик |

**Инструменты** (`search/tools.py`):

| Инструмент | Что ищет |
|------------|----------|
| `search_roundtrip_tickets` | Авиа, РЖД/Tutu, автобус |
| `search_culture_events` | Афиша, музеи, выставки (по району) |
| `search_dining_and_transport` | Рестораны (много ссылок) + транспорт |

Запросы дополняются **`search_context`** из опросника (`search/context.py`). Постфильтрация сниппетов — `config/settings.py` → `SEARCH_FILTERS`.

**Стек:** LangGraph 0.2+, LangChain 0.3, OpenAI `gpt-4o-mini` (`agents/llm.py`), Pydantic, SQLite, **ddgs** / Tavily, PyYAML (eval).

### Eval (уровни проверки)

| Уровень | Модуль | Что проверяет |
|---------|--------|----------------|
| 1 | `eval/checks/deterministic.py` | JSON-схема `FinalProgram`, ссылки, маркеры билетов |
| 2 | `eval/checks/tools.py` | Вызовы tools, `live_data`, `results_count` |
| 3 | `eval/checks/llm_judge.py` | Опционально: цены со ссылками, город (`--with-llm`) |
| 4 | `eval/checks/regression.py` | Метрики vs `eval/golden/*.json` |

Датасет: `eval/dataset/smoke.yaml`. Запуск: `python3 -m eval --suite smoke`.

---

## Проектирование агента

### Какую задачу решает агент?

По городу, датам, предпочтениям (опросник) и городу отправления агент **собирает актуальную информацию из интернета**, формирует **структурированную программу** из пяти разделов и сохраняет версии в SQLite. Пользователь **утверждает** результат или запрашивает доработку.

### Кто будет пользоваться агентом?

**Частные путешественники** и **менеджеры поездок** (самостоятельный туризм): один запрос и опросник вместо ручного поиска на Aviasales, Афише и картах; возврат к поездке, частичный пересбор разделов, просмотр сохранённой программы.

### С какими внешними системами и данными работает агент?

| Система | Назначение |
|---------|------------|
| **OpenAI API** (ProxyAPI) | Researcher, writer, опционально LLM-judge в eval |
| **SQLite** (`DATABASE_PATH`) | `trips`, `trip_preferences`, `user_profile`, `itinerary_versions`, `tool_runs` |
| **Tavily API** (опционально) | Веб-поиск с ответом-сводкой |
| **DuckDuckGo** (`ddgs`, ru-ru) | Веб-поиск по умолчанию |
| **LangFuse** (опционально) | Трейсы запусков LangGraph/LLM/tools (self-hosted через Docker) |
| **LangSmith** (опционально) | Трейсы графа (`observability/tracing.py`) |
| **Aviasales / Яндекс.Путешествия** | Сниппеты по авиабилетам |
| **РЖД / Tutu.ru** | Поезда |
| **Bus.ru и аналоги** | Автобусы |
| **Афиша / Kassir.ru** | Мероприятия |
| **2GIS / Яндекс.Карты / TripAdvisor** | Рестораны и транспорт |

Прямые партнёрские API этих сервисов **не подключены** — агент находит публичные страницы через поиск.

### Почему нужен именно агент, а не workflow?

- **Нестабильный ввод**: даты и города в свободной форме, опросник и уточнения в запросе.
- **Многошаговый сбор**: researcher решает, какие tools вызвать; critic и пользователь могут инициировать повтор.
- **Синтез из шума**: LLM отбирает факты из `digest`, группирует по районам.
- **Память и итерации**: SQLite, частичный пересбор, HITL без потери контекста поездки.

Детерминированный пайплайн «3 HTTP-запроса → шаблон» не покрывает вариативность запросов и качество сниппетов.

### Почему здесь не нужен RAG

В этом проекте RAG **не даёт ключевой пользы**, потому что задача требует **актуальных данных** (события, цены, расписания) и **ссылок на первоисточники**. Поэтому основной подход — web-search tools + структурирование результата:

- Источник знаний — **живой веб‑поиск** (`ddgs` / Tavily) и ссылки в `digest`, а не статичный корпус документов.
- SQLite здесь — **память/версии/профиль**, а не база знаний для retrieval.
- RAG усложнит систему (эмбеддинги, актуализация, качество корпуса), но не решит проблему «актуальность» — всё равно нужен web.
Если расширять проект дальше, RAG был бы уместен для локальной базы: FAQ по визам/транспорту, чек‑листы, правила пересадок, «best practices» по городу и т.п.

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
- `LANGFUSE_HOST=http://localhost:3000`
- `LANGFUSE_PUBLIC_KEY=...`
- `LANGFUSE_SECRET_KEY=...`

3) Запустить `python3 main.py` — трейсинг пойдёт через LangChain callbacks.

### LangSmith (опционально, параллельно)

LangSmith можно включить одновременно с LangFuse:

- `LANGCHAIN_TRACING_V2=true`
- `LANGCHAIN_API_KEY=...`
- `LANGCHAIN_PROJECT=tourist-assistant`

---

## Метрики (для README диплома)

- **Success rate**: `python3 -m eval --suite smoke` (10 кейсов)
- **Latency p95 / cost per run**: после нескольких запусков CLI:

```bash
python3 -m scripts.metrics_report --limit 50
```

Примечание: стоимость/токены пишутся через `get_openai_callback()` и могут быть пустыми для не-OpenAI провайдеров.

---

## Security checklist

Отметки: ✅ done / ➖ n/a / ⏳ open

- ✅ **Secrets**: ключи только через env (`.env` в `.gitignore`), шаблон — `.env.example`.
- ✅ **Prompt-injection (user input)**: `sanitize_and_validate` + паттерны `INJECTION_PATTERNS`.
- ✅ **Tool safety**: tools не выполняют произвольный код и не пишут файлы; выход — строковый payload.
- ⏳ **Allowlist доменов**: есть смысловой фильтр `SEARCH_FILTERS`, но нет жёсткой allowlist доменов.
- ⏳ **PII**: в SQLite сохраняются запрос и предпочтения; нет маскирования/политики хранения.
- ✅ **Ошибки внешних систем**: tool error попадает в `ToolMessage`, граф не падает, `live_data=false` в логах.
- ⏳ **Rate limiting**: есть таймаут поиска (`SEARCH_TIMEOUT`), но нет общего лимита попыток/бюджета.
- ➖ **Multi-user auth**: не применимо (локальный CLI).

### Сложные и нестандартные ситуации

| Ситуация | Обработка |
|----------|-----------|
| **Пустой или нерелевантный поиск** | Фильтр по `SEARCH_FILTERS` + fallback top-8; предупреждение в payload tool |
| **Ошибка поиска / сети** | `ToolMessage` с ошибкой; граф не падает, `tool_runs` с `live_data=false` |
| **Prompt-injection во вводе** | `input_validation.sanitize_and_validate` |
| **Галлюцинации цен** | Промпт: цены только из `digest`; иначе «уточните на сайте» + ссылка |
| **Critic не прошёл** | До 2 повторов researcher; затем всё равно HITL с замечаниями |
| **Пользователь не утвердил (n)** | Пересбор или сохранение черновика (`status=review`) |
| **Повторный запуск без опросника** | `user_profile` + `trip_preferences`; fallback из последней поездки |
| **Конфликт категорий** (музей в «Билетах») | Постфильтрация `SEARCH_FILTERS` в `search/web.py` |
| **Даты в далёком будущем** | В поиске может не быть цен — в ответе ссылки «уточните на сайте» |

### Как понять, что агент работает хорошо?

| Критерий | Приемлемый результат |
|----------|----------------------|
| **Полнота программы** | Все 5 разделов заполнены; в «Билетах» есть 3 блока со ссылками: «Самолёт», «Поезд», «Автобус» |
| **Опора на поиск** | В «Питании» ≥ 6 ресторанов со ссылками из digest; мероприятия сгруппированы по району |
| **Надёжность и воспроизводимость** | `python3 -m unittest discover -s tests -v` и `python3 -m eval --suite smoke` проходят; в «Продолжить» видна поездка с версией программы |

---

## Структура репозитория

```
tourist-assistant/
├── main.py                 # Точка входа: python3 main.py
├── cli/app.py              # Меню, опросник, invoke графа, сохранение в БД
├── config/settings.py      # .env, SEARCH_FILTERS, лимиты LLM/поиска
├── models/
│   ├── schemas.py          # FinalProgram, входы tools
│   └── state.py            # AgentState
├── input_validation.py     # sanitize_and_validate
├── search/
│   ├── web.py              # Tavily / ddgs, digest
│   ├── tools.py            # @tool, TOOLS, TOOL_MAP
│   ├── context.py          # search_context сессии
│   └── tool_logging.py     # разбор payload для tool_runs
├── agents/
│   ├── llm.py              # ChatOpenAI, llm_with_tools, llm_final
│   ├── nodes.py            # researcher, executor, writer
│   ├── graph.py            # сборка LangGraph, app
│   ├── critic.py
│   ├── human_review.py
│   └── print_program.py
├── planning/rebuild.py       # rebuild_scope, merge_program
├── db/                     # schema.sql, repository
├── onboarding/             # опросник, TripPreferences
├── observability/tracing.py
├── eval/                   # python3 -m eval --suite smoke
├── scripts/render_graph.py # PNG графа → docs/assets/graph.png
├── docs/assets/graph.png   # схема для README
├── tests/
├── data/                   # trips.db (в .gitignore)
├── requirements.txt
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
