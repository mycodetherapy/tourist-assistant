-- SQLite-схема: поездки, предпочтения, версии программы, лог tools, артефакты поиска.

CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    dates TEXT NOT NULL,
    origin_city TEXT NOT NULL,
    user_query TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trip_preferences (
    trip_id INTEGER PRIMARY KEY REFERENCES trips(id) ON DELETE CASCADE,
    preferences_json TEXT NOT NULL
);

-- Профиль локального пользователя (CLI): последние ответы опросника
CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    preferences_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS itinerary_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    scope TEXT NOT NULL,
    program_json TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(trip_id, version)
);

CREATE TABLE IF NOT EXISTS tool_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    itinerary_version_id INTEGER REFERENCES itinerary_versions(id) ON DELETE SET NULL,
    tool_name TEXT NOT NULL,
    args_json TEXT,
    provider TEXT,
    live_data INTEGER,
    results_count INTEGER,
    raw_results_count INTEGER,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS section_artifacts (
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    section TEXT NOT NULL,
    digest TEXT,
    payload_json TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (trip_id, section)
);

-- Метрики прогонов агента (latency / tokens / cost). Источник tokens/cost: OpenAI callback (если доступен).
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    rebuild_scope TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    total_cost_usd REAL,
    created_at TEXT NOT NULL
);

-- Оценки пунктов подборки (лайк/дизлайк). Ключ item_key — по тексту пункта.
CREATE TABLE IF NOT EXISTS program_item_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    itinerary_version_id INTEGER REFERENCES itinerary_versions(id) ON DELETE SET NULL,
    section TEXT NOT NULL,
    item_index INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    vote INTEGER NOT NULL CHECK (vote IN (1, -1)),
    updated_at TEXT NOT NULL,
    UNIQUE(trip_id, section, item_key)
);

CREATE INDEX IF NOT EXISTS idx_trips_updated ON trips(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_runs_trip ON tool_runs(trip_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_trip ON agent_runs(trip_id);
CREATE INDEX IF NOT EXISTS idx_program_feedback_trip ON program_item_feedback(trip_id);
