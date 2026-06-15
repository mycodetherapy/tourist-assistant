import { Alert, AutoComplete, Button, Spin } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { parseCoordinateQuery } from "../utils/parseCoordinateQuery";
import {
  isYandexMapsConfigured,
  loadYandexMaps,
  type YMapInstance,
} from "../utils/yandexMapsLoader";

export interface MapPoint {
  lat: number;
  lon: number;
}

export interface GeocodeHit {
  lat: number;
  lon: number;
  label: string;
}

interface RouteAnchorMapPickerProps {
  /** Начальный центр карты (город); не меняется при выборе точки. */
  center: MapPoint;
  value: MapPoint | null;
  label?: string;
  onChange: (point: MapPoint, meta?: { label: string; source: "map" | "address" | "coordinates" }) => void;
  onGeocode?: (query: string) => Promise<GeocodeHit[]>;
  onReverseGeocode?: (lat: number, lon: number) => Promise<string | null>;
  height?: number;
  hint?: string;
}

function formatCoordLabel(point: MapPoint): string {
  return `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`;
}

/** Карта Яндекс.Карт: поиск адреса/координат + клик задаёт базовую точку. */
export function RouteAnchorMapPicker({
  center,
  value,
  label = "",
  onChange,
  onGeocode,
  onReverseGeocode,
  height = 320,
  hint = "Введите адрес или координаты, либо нажмите на карту",
}: RouteAnchorMapPickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<YMapInstance | null>(null);
  const placemarkRef = useRef<unknown>(null);
  const mapReadyRef = useRef(false);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const onReverseGeocodeRef = useRef(onReverseGeocode);
  onReverseGeocodeRef.current = onReverseGeocode;
  const valueRef = useRef(value);
  valueRef.current = value;

  const [loading, setLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);
  const [resolvingClick, setResolvingClick] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState(label);
  const searchQueryRef = useRef(searchQuery);
  searchQueryRef.current = searchQuery;
  const [suggestions, setSuggestions] = useState<{ value: string; label: string; hit: GeocodeHit }[]>(
    [],
  );

  useEffect(() => {
    setSearchQuery(label);
  }, [label]);

  const updatePlacemark = useCallback(async (point: MapPoint, labelText: string) => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) {
      return;
    }
    const ymaps = await loadYandexMaps();
    if (placemarkRef.current) {
      map.geoObjects.remove(placemarkRef.current);
      placemarkRef.current = null;
    }
    const mark = new ymaps.Placemark(
      [point.lat, point.lon],
      {
        hintContent: "Базовая точка",
        balloonContent: labelText.trim() || "Базовая точка",
      },
      { preset: "islands#redDotIcon" },
    );
    placemarkRef.current = mark;
    map.geoObjects.add(mark);
  }, []);

  const focusPoint = useCallback(
    (point: MapPoint, labelText: string, zoom = 16) => {
      const map = mapRef.current;
      if (map) {
        map.setCenter([point.lat, point.lon], zoom);
      }
      void updatePlacemark(point, labelText);
    },
    [updatePlacemark],
  );

  const applyPoint = useCallback(
    (
      point: MapPoint,
      meta: { label: string; source: "map" | "address" | "coordinates" },
      zoom = 16,
    ) => {
      const labelText = meta.label.trim() || formatCoordLabel(point);
      setSearchQuery(labelText);
      onChangeRef.current(point, { label: labelText, source: meta.source });
      focusPoint(point, labelText, zoom);
    },
    [focusPoint],
  );

  const resolveAddressLabel = useCallback(async (point: MapPoint): Promise<string> => {
    const reverse = onReverseGeocodeRef.current;
    if (!reverse) {
      return formatCoordLabel(point);
    }
    try {
      const label = await reverse(point.lat, point.lon);
      if (label?.trim()) {
        return label.trim();
      }
    } catch {
      /* fallback to coordinates */
    }
    return formatCoordLabel(point);
  }, []);

  const handleMapClick = useCallback(
    async (point: MapPoint) => {
      const fallback = formatCoordLabel(point);
      applyPoint(point, { label: fallback, source: "map" });
      setResolvingClick(true);
      try {
        const resolved = await resolveAddressLabel(point);
        if (resolved !== fallback) {
          applyPoint(point, { label: resolved, source: "map" });
        }
      } finally {
        setResolvingClick(false);
      }
    },
    [applyPoint, resolveAddressLabel],
  );

  const runSearch = async (rawQuery: string) => {
    const query = rawQuery.trim();
    if (!query) {
      return;
    }

    const coords = parseCoordinateQuery(query);
    if (coords) {
      applyPoint({ lat: coords.lat, lon: coords.lon }, { label: coords.label, source: "coordinates" });
      setSuggestions([]);
      return;
    }

    if (!onGeocode) {
      setError("Геокодинг недоступен");
      return;
    }

    setSearchLoading(true);
    setError(null);
    try {
      const hits = await onGeocode(query);
      if (hits.length === 0) {
        setError("Ничего не найдено. Уточните адрес или введите координаты (широта, долгота).");
        return;
      }
      if (hits.length === 1) {
        const hit = hits[0];
        applyPoint({ lat: hit.lat, lon: hit.lon }, { label: hit.label, source: "address" });
        setSuggestions([]);
        return;
      }
      setSuggestions(
        hits.map((hit) => ({
          value: hit.label,
          label: hit.label,
          hit,
        })),
      );
    } catch {
      setError("Не удалось найти адрес. Проверьте подключение или введите координаты.");
    } finally {
      setSearchLoading(false);
    }
  };

  useEffect(() => {
    if (!isYandexMapsConfigured()) {
      setError("Задайте VITE_YANDEX_MAPS_API_KEY в web/.env");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    mapReadyRef.current = false;

    loadYandexMaps()
      .then((ymaps) => {
        if (cancelled || !containerRef.current) {
          return;
        }
        mapRef.current?.destroy();
        placemarkRef.current = null;

        const start = valueRef.current ?? center;
        const map = new ymaps.Map(
          containerRef.current,
          {
            center: [start.lat, start.lon],
            zoom: valueRef.current ? 16 : 13,
            controls: ["zoomControl", "geolocationControl"],
          },
          { suppressMapOpenBlock: true },
        );
        mapRef.current = map;
        mapReadyRef.current = true;

        map.events.add("click", (event) => {
          const coords = event.get("coords");
          void handleMapClick({ lat: coords[0], lon: coords[1] });
        });

        if (valueRef.current) {
          void updatePlacemark(valueRef.current, searchQueryRef.current || label);
        }

        setLoading(false);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      mapReadyRef.current = false;
      mapRef.current?.destroy();
      mapRef.current = null;
      placemarkRef.current = null;
    };
  }, [center.lat, center.lon, handleMapClick, label, updatePlacemark]);

  useEffect(() => {
    if (!mapReadyRef.current || value) {
      return;
    }
    mapRef.current?.setCenter([center.lat, center.lon], 13);
  }, [center.lat, center.lon, value]);

  useEffect(() => {
    if (!value || !mapReadyRef.current) {
      return;
    }
    focusPoint(value, label.trim() || formatCoordLabel(value));
  }, [value?.lat, value?.lon, label, focusPoint]);

  if (error && !isYandexMapsConfigured()) {
    return <Alert type="warning" showIcon message={error} />;
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-gray-500">{hint}</p>
      <div className="flex items-center gap-2 rounded-t-lg border border-b-0 border-gray-200 bg-white p-1.5">
        <AutoComplete
          className="min-w-0 flex-1 [&_.ant-select]:!w-full [&_.ant-select-selector]:!rounded-md [&_.ant-select-selector]:!border-gray-200"
          value={searchQuery}
          options={suggestions}
          onChange={setSearchQuery}
          onSelect={(selected) => {
            const option = suggestions.find((item) => item.value === selected);
            if (option) {
              applyPoint(
                { lat: option.hit.lat, lon: option.hit.lon },
                { label: option.hit.label, source: "address" },
              );
              setSuggestions([]);
            }
          }}
          placeholder="Адрес или объект"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void runSearch(searchQuery);
            }
          }}
        />
        <Button
          type="primary"
          loading={searchLoading || resolvingClick}
          className="shrink-0"
          onClick={() => void runSearch(searchQuery)}
        >
          Найти
        </Button>
      </div>
      {error && isYandexMapsConfigured() && (
        <Alert type="warning" showIcon className="!mb-0" message={error} closable onClose={() => setError(null)} />
      )}
      <div className="relative overflow-hidden rounded-b-lg border border-gray-200">
        {(loading || resolvingClick) && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center bg-white/70"
            style={{ height }}
          >
            <Spin tip={resolvingClick ? "Определяем адрес…" : undefined} />
          </div>
        )}
        <div ref={containerRef} style={{ height, width: "100%" }} />
      </div>
    </div>
  );
}
