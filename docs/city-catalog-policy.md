# Политика каталога городов (OSM / OSRM)

Ветка: `feat/maplibre-osrm`. VPS сейчас: **4 ГБ RAM / 50 ГБ** (~5 пользователей).

## Роли данных

| Артефакт | Где готовится | На VPS |
|----------|---------------|--------|
| FO Geofabrik `.osm.pbf` | **только Mac** | не обязателен (можно не хранить) |
| `extract.osm.pbf` + `poi.sqlite` | Mac → rsync | да |
| `osrm/*.osrm*` | Mac → rsync | да (файлы) |
| `osrm-routed` | — | **эфемерный** `docker run` на время geometry |

Geofabrik — это **файлы + разовые docker job’ы**, не постоянно крутящийся сервис.

## Полки

### A — hot (всегда готовые файлы на диске)

OSRM-граф на NVMe; при сборке маршрута worker поднимает эфемерный роутер.

Состав:

- Поволжье (8): Казань, Йошкар-Ола, Самара, НН, Ижевск, Тольятти, Кострома (`central`), Ульяновск
- Central+NW: Москва, Ярославль, Владимир, Суздаль, Сергиев Посад, Тула, Тверь, Калуга, Санкт-Петербург

### B — warm (каталог, extract+poi prebuild; OSRM по нужде)

Списки в `config/city_packs.yaml` (`tier: warm`). OSRM-граф можно дособрать на Mac и залить, либо позже lazy.

### C — вне каталога

Wikidata + iframe Яндекса. Заявка → ручной accept → появление в B/A.

## Runtime на 4 ГБ (`OSRM_MODE=ephemeral`)

1. File lock (один роутер за раз).
2. `docker run --rm` с графом города на общей docker-сети.
3. HTTP `/route/v1/foot/...`.
4. `docker rm -f`.

Нужны: `docker.sock` у worker, `OSRM_HOST_DATA_CITIES` = **абсолютный путь на хосте** к `data/cities`.

Масштаб позже: `OSRM_MODE=http` + несколько always-on / `OSRM_URL_BY_SLUG`.

## Обновления

- FO/extract/osrm: на Mac, раз в 30–90 дней или перед новым городом.
- На VPS: rsync `data/cities/<slug>/`, без тяжёлого extract на 4 ГБ.

## Заявки

Таблица `city_requests` + `POST /api/city-requests` + CLI `python scripts/city_requests_cli.py`.
