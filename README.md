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

### Переменные окружения

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `OPENAI_API_KEY` | Да* | Ключ для LLM (*не нужен для `unittest` и `eval --suite smoke` без `--with-llm`) |
| `PROXY_BASE_URL` | Нет | По умолчанию `https://openai.api.proxyapi.ru/v1` |
| `TAVILY_API_KEY` | Нет | Точнее веб-поиск; без ключа — DuckDuckGo (`ddgs`, регион `ru-ru`) |
| `DATABASE_PATH` | Нет | SQLite, по умолчанию `data/trips.db` |
| `LANGCHAIN_TRACING_V2` | Нет | `true` — трейсы в [LangSmith](https://smith.langchain.com) |
| `LANGCHAIN_API_KEY` | Нет | Ключ LangSmith |
| `LANGCHAIN_PROJECT` | Нет | Имя проекта (по умолчанию `tourist-assistant`) |

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
