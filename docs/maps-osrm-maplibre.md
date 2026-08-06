# План: MapLibre + OSRM (ветка `feat/maplibre-osrm`)

Цель: интерактивная карта (клики, follow GPS) и пешая линия по улицам **без** платного Router API Яндекса.  
Текущий iframe Яндекс.Карт остаётся **дефолтом и фолбеком** до явного включения флага.

Связанный дизайн/фон: этот файл — **исполняемый план**. Код-каркас уже в ветке.

---

## 0. Правила ветки и фолбека

| Правило | Как |
|---------|-----|
| Ветка | Вся работа только в `feat/maplibre-osrm` (от `develop`). В `develop`/`main` — через PR. |
| UI по умолчанию | `RouteMapEmbed` (iframe Яндекса) — **как сейчас в проде** |
| Новый UI | `RouteMapLibre` только при `VITE_MAP_PROVIDER=maplibre` |
| Worker без OSRM | Сборка **не ломается**: `maps_route_url` + маркеры как раньше; `route_geometry` = `null` |
| Deep link | Кнопка «Открыть в Яндекс.Картах» сохраняется в обоих режимах |

Переключение локально:

```bash
# web/.env или корневой .env (для Vite)
VITE_MAP_PROVIDER=maplibre

# worker
OSRM_BASE_URL=http://127.0.0.1:5000
```

Прод до готовности фазы 4: **не** ставить `VITE_MAP_PROVIDER=maplibre`, OSRM profile можно не поднимать.

---

## 1. Что если для города нет графа OSRM?

### При создании / пересборе маршрута (worker)

```
есть OSRM_BASE_URL?
   нет  → как сейчас: maps_route_url, route_map_*, без route_geometry
   да   → HTTP /route/v1/foot/…
            │
            ├─ Ok → route_geometry + distance/duration в TripRouteCase
            └─ ошибка / NoRoute / таймаут / граф другого города
                 → log warning, route_geometry=null, сборка УСПЕШНА
                 → maps_route_url всё равно заполнен
```

**Сборка маршрута не зависит от наличия графа.** Нет графа ≠ ошибка для пользователя.  
Нет только «красивой» линии по тротуарам в MapLibre (будут прямые между точками) и точных `route_distance_m` от OSRM.

Типичные причины «нет геометрии» при включённом `OSRM_BASE_URL`:

| Ситуация | Поведение |
|----------|-----------|
| Граф не собран для slug | OSRM отвечает ошибкой / NoRoute → `null` |
| Поднят граф Казани, сборка Самары | Точки вне графа → NoRoute → `null` |
| OSRM контейнер down | httpx error → `null` |
| `OSRM_BASE_URL` пуст | клиент сразу `null`, без HTTP |

### В UI

| `VITE_MAP_PROVIDER` | Есть `route_geometry` | Нет `route_geometry` |
|---------------------|----------------------|----------------------|
| unset / `yandex` | iframe Яндекса (линия строит виджет) | iframe Яндекса |
| `maplibre` | линия по улицам | прямые сегменты + маркеры + deep link |

---

## 2. Процесс создания нового графа OSRM

Граф = производное от **city pack extract** (тот же `extract.osm.pbf`, что для POI).

### Предусловия

1. Город есть в [`config/city_packs.yaml`](../config/city_packs.yaml).
2. Собран pack: `data/cities/<slug>/extract.osm.pbf` (+ обычно `poi.sqlite`).
   - Если extract нет: `bash scripts/city_pack_prepare.sh <slug>` (нужен FO PBF через `fo_ensure.sh`).

### Сборка графа (один раз на город, потом при обновлении extract)

```bash
bash scripts/osrm_prepare.sh <slug>
# Пример: bash scripts/osrm_prepare.sh samara
```

Скрипт:

1. Копирует `extract.osm.pbf` → `data/cities/<slug>/osrm/<slug>.osm.pbf`
2. Docker `osrm-extract -p /opt/foot.lua`
3. `osrm-partition` + `osrm-customize` (MLD)
4. Результат: `data/cities/<slug>/osrm/<slug>.osrm*` (~десятки MB на город)

Время: обычно **1–5 минут** на городской extract (не на весь FO).

### Запуск роутера

**MVP (один город на контейнер):**

```bash
OSRM_DATASET=kazan docker compose --profile osrm up -d osrm
# в .env worker:
OSRM_BASE_URL=http://osrm:5000   # из контейнера worker
# или локально: http://127.0.0.1:5000
```

Проверка:

```bash
curl -s "http://127.0.0.1:5001/route/v1/foot/49.122,55.787;49.135,55.796?overview=false" | head -c 300
# ожидается "code":"Ok"
# (хост-порт по умолчанию 5001 — на macOS :5000 часто занят AirPlay)
```

### Когда обновлять граф

- После пересборки city pack (новый `extract.osm.pbf`)
- Если маршруты «дыры» / NoRoute на окраине (увеличить `extract_buffer_km` в yaml → пересобрать pack → `osrm_prepare`)

### Несколько городов (после MVP)

| Вариант | Когда |
|---------|--------|
| A. Несколько контейнеров `osrm` (разные `OSRM_DATASET` / порты) + выбор URL по slug в worker | 8 городов, VPS ≥ ~2–3 GB свободно под OSRM |
| B. Один граф на FO Volga | Проще URL, больше RAM (~2–4 GB) |
| C. Пока один город (Казань) в OSRM; остальные — iframe / прямые | Старт с 10–15 юзерами |

**В плане фаз: сначала C (Казань), потом A.**

---

## 3. Фазы реализации (исполнение по порядку)

Каждая фаза = отдельный PR в `feat/maplibre-osrm` → merge в ветку, затем общий PR в `develop` когда фаза 4 зелёная.  
Или один длинный PR с чеклистом — но фазы ниже **нельзя пропускать**.

### Фаза 0 — зафиксировать каркас (уже в ветке) ✅

- [x] Ветка `feat/maplibre-osrm`
- [x] `search/osrm/client.py` + тест
- [x] Хук в `_maps_route_fields` (мягкий)
- [x] `scripts/osrm_prepare.sh`, compose profile `osrm`
- [x] `RouteMapLibre` + флаг; **дефолт UI = Яндекс iframe**
- [x] Документ плана

**Done when:** на `develop`-поведении без флагов UI неотличим от iframe; `unittest tests.test_osrm_client` зелёный.

### Фаза 1 — OSRM локально на Казани (инфра)

**Задачи**

1. [x] Пересобрать граф: `bash scripts/osrm_prepare.sh kazan`
2. [x] `OSRM_DATASET=kazan docker compose --profile osrm up -d osrm` (хост-порт **5001** — на macOS :5000 занят AirPlay)
3. [x] `curl` / Python client → `code Ok`
4. [x] В локальном `.env`: `OSRM_BASE_URL=http://127.0.0.1:5001` (не коммитить)
5. [ ] Собрать тестовую прогулку по Казани; в JSON case проверить `route_geometry.coordinates.length > 2`
6. [ ] Собрать прогулку по городу **без** графа (или с выключенным OSRM) — убедиться что сборка ок, `route_geometry` null

**Done when:** Казань даёт geometry; другой город / down OSRM — тихий fallback без падения run.

**Оценка:** 0.5–1 день.

### Фаза 2 — довести MapLibre до usable MVP

**Задачи**

1. [x] Включить локально `VITE_MAP_PROVIDER=maplibre` (корневой `.env`, Vite `envDir`)
2. [ ] Полировка UX: высота карты, touch vs scroll страницы, легенда S / номера
3. [x] Клик по маркеру стопа → `poiFact.open` (через `ProgramTabs` → `RouteMapView`)
4. [ ] Follow: кнопка геолокации включает/выключает `watchUserLocation`; ошибка HTTPS понятна (smoke на телефоне)
5. [x] Нет `route_geometry` → прямые + hint «линия приближённая»
6. [x] Регрессия: без флага снова iframe (дефолт `yandex`)

**Done when:** на телефоне по HTTPS можно идти с follow по Казани; клик по маркеру работает; без флага — старый UI.

**Оценка:** 1–2 дня.

### Фаза 3 — multi-city OSRM (операционка)

**Задачи**

1. [ ] `osrm_prepare.sh` для всех `default_packs` в `city_packs.yaml` (скрипт batch или цикл)
2. [ ] Решение по деплою: **A** несколько сервисов compose **или** выбор URL по slug  
   Рекомендация: compose template / отдельные сервисы `osrm-kazan`, `osrm-samara`, … за internal network; worker: `OSRM_BASE_URL` → map `slug → http://osrm-<slug>:5000` (env `OSRM_URL_TEMPLATE` или yaml)
3. [ ] Worker: резолв slug города поездки → нужный OSRM base URL; unknown slug → skip geometry
4. [ ] Документировать в README объём RAM на VPS
5. [ ] CI/prod: profile `osrm` опционален; графы на volume `data/cities` (как poi.sqlite)

**Done when:** сборка Самара/НН даёт geometry при поднятых графах; неизвестный город — без падения.

**Оценка:** 1–2 дня (+ время prepare на каждый город).

### Фаза 4 — включение на prod

**Задачи**

1. [ ] Staging/prod: залить `osrm/` артефакты на VPS (rsync рядом с `poi.sqlite`)
2. [ ] Поднять `osrm` в `deploy/docker-compose.prod.yml --profile osrm`
3. [ ] `OSRM_BASE_URL` в prod `.env` worker
4. [ ] Сборка web с `VITE_MAP_PROVIDER=maplibre` (secret/CI build-arg)
5. [ ] Smoke: Казань geometry + follow; откат: убрать `VITE_MAP_PROVIDER` → снова iframe без редеплоя api (только web rebuild) **или** держать оба образа
6. [ ] Юридическое: атрибуция OSM на карте (MapLibre/OpenFreeMap добавляет сами); при необходимости строка в Privacy/Terms про OSM-тайлы

**Done when:** прод на MapLibre; iframe доступен откатом флага; метрики ошибок OSRM в логах worker приемлемы.

**Оценка:** 0.5–1 день + окно деплоя.

### Фаза 5 — follow / продукт (после стабилизации карты)

**Задачи**

1. [ ] Snap к линии (OSRM `/match` или клиентский nearest-point) — уменьшить дрожь GPS
2. [ ] «До следующей остановки N м» в UI
3. [ ] Хук под будущие текст/аудио у стопа (proximity)
4. [ ] Убрать или сузить зависимость от Яндекс JS API на picker (отдельный эпик, не блокер)

**Done when:** follow пригоден для реальной прогулки 30–60 мин без ручных костылей.

**Оценка:** 2–4 дня.

---

## 4. Критерии качества (общие)

1. Без флагов поведение = текущий iframe (регрессий нет).
2. Ошибка OSRM никогда не валит `graph_run` / partial rebuild.
3. `route_geometry` — валидный GeoJSON LineString `[lon,lat]` или отсутствует.
4. На 10–15 пользователей: OSRM ≤ ~0.5 GB RAM на город; follow не бьёт сервер.

---

## 5. Порядок следующего шага

**Сейчас выполнять фазу 1** (OSRM на Казани + проверка geometry в case).  
Фазу 2 не начинать, пока фаза 1 не зелёная.

Команды старта фазы 1:

```bash
git checkout feat/maplibre-osrm
bash scripts/osrm_prepare.sh kazan
OSRM_DATASET=kazan docker compose --profile osrm up -d osrm
# в .env: OSRM_BASE_URL=http://127.0.0.1:5001 (worker на хосте)
# собрать прогулку Казань → проверить route_geometry в program
```
