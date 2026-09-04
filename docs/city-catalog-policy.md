# Политика каталога городов (OSM / OSRM)

VPS: **~4 ГБ RAM / ~30 ГБ** диск. Self-serve OSRM для зарегистрированных пользователей.

## Роли данных

| Артефакт | Где готовится | На VPS |
|----------|---------------|--------|
| FO Geofabrik `.osm.pbf` | Mac **или** VPS (`fo_ensure` / nightly) | **нужен subset** для self-serve extract |
| `extract.osm.pbf` + `poi.sqlite` | Mac rsync **или** VPS worker | да |
| `osrm/*.osrm*` | Mac rsync **или** VPS `prepare_osrm` | да |
| `osrm-routed` | — | **эфемерный** `docker run` на время geometry |

## Полки

### A — hot / ready (есть `*.osrm.mldgr`)

Чипы `GET /api/cities/osrm-ready`. Ephemeral роутер при сборке маршрута.

### B — eligible (каталог + FO на диске, OSRM нет)

`GET /api/cities/osrm-eligible`. Пользователь с подтверждённым email ставит `POST /api/osrm-prepares`. Бесплатный режим: лимит **3** новых города на аккаунт. BYOK с сохранённым ключом: без этого лимита (остаются диск, cap городов на сервере и rate limit очереди).

### C — вне каталога / без FO

Wikidata + iframe. Wishlist: `POST /api/city-requests`.

## Self-serve

1. Email verified (Resend / письмо) или Google OAuth.
2. Выбор города из eligible.
3. Worker: `fo_ensure` → `city_pack_prepare` → `osrm_prepare`.
   Для `docker run -v` из worker нужен **путь хоста**: `TOURIST_HOST_DATA_DIR` (локально `${PWD}/data`, VPS `/opt/tourist-assistant/data`). `TOURIST_DATA_DIR=/app/data` — только I/O внутри контейнере.
4. Прогресс и уведомление в UI. При ошибке квота **бесплатного** режима возвращается (BYOK квоту не тратит).
5. Диск: hard stop если свободно &lt; `OSRM_PREPARE_MIN_FREE_GB` (default 5). Soft-cap городов: `OSRM_PREPARE_MAX_CITIES` (40).
6. Если у пользователя уже есть маршруты по городу и граф OSRM обновился (mtime `*.osrm.mldgr` новее `itinerary_versions.created_at`) — на странице прогулки баннер «Карта обновилась» + CTA пересбор (`GET /api/trips/:id/osrm-update`).

## Runtime ephemeral

См. прежние правила: `OSRM_MODE=ephemeral`, `docker.sock`, `OSRM_HOST_DATA_CITIES`.

## Обновления

- Nightly staggered: `scripts/osrm_nightly_refresh.py` (окно 02–06 Europe/Moscow, цикл ~14 дней: 1 FO / ночь, затем 2 города / ночь).
- `fo_ensure.sh` качает во временный файл и подменяет PBF только после проверки; в образе worker нужен `curl`.
- При ошибке скачивания FO/город остаются в очереди (не сдвигаются).
- User prepare и nightly делят lock `tourist:lock:osrm_prepare`.

## Заявки вне каталога

Таблица `city_requests` + CLI `python scripts/city_requests_cli.py` — без авто-extract.
