import { useQuery } from "@tanstack/react-query";
import { Button, Checkbox, Spin } from "antd";
import { useMemo, useState } from "react";
import { geocodeQuery, reverseGeocodeQuery } from "../api/trips";
import {
  guestGeocodeQuery,
  guestReverseGeocodeQuery,
} from "../api/guest";
import type { RouteAnchor } from "../api/types";
import { RouteAnchorMapPicker, type MapPoint } from "./RouteAnchorMapPicker";

interface NewTripAnchorFieldsProps {
  city: string;
  value: RouteAnchor | null | undefined;
  onChange: (anchor: RouteAnchor | null) => void;
  disabled?: boolean;
  guestMode?: boolean;
}

const FALLBACK_CENTER: MapPoint = { lat: 55.75, lon: 37.62 };

/** Опциональная базовая точка при создании прогулки (до trip_id). */
export function NewTripAnchorFields({
  city,
  value,
  onChange,
  disabled = false,
  guestMode = false,
}: NewTripAnchorFieldsProps) {
  const [loopEnd, setLoopEnd] = useState(Boolean(value?.loop_end));
  const cityTrimmed = city.trim();
  const geocodeFn = guestMode ? guestGeocodeQuery : geocodeQuery;
  const reverseGeocodeFn = guestMode ? guestReverseGeocodeQuery : reverseGeocodeQuery;

  const cityCenterQuery = useQuery({
    queryKey: [guestMode ? "guest" : "new-trip", "city-center", cityTrimmed],
    queryFn: () => geocodeFn(cityTrimmed, cityTrimmed),
    enabled: cityTrimmed.length >= 2,
  });

  const mapCenter = useMemo((): MapPoint => {
    const hit = cityCenterQuery.data?.results[0];
    if (hit) {
      return { lat: hit.lat, lon: hit.lon };
    }
    return FALLBACK_CENTER;
  }, [cityCenterQuery.data]);

  const mapValue = value ? { lat: value.lat, lon: value.lon } : null;

  return (
    <div className="mt-4 space-y-3 rounded-lg border border-gray-100 bg-gray-50 p-3">
      <p className="text-sm font-medium text-gray-700">Базовая точка (необязательно)</p>
      <p className="text-xs text-gray-500">
        Отель или место проживания — маршруты на карте начнутся от неё после сборки.
      </p>
      {cityCenterQuery.isLoading ? (
        <div className="flex h-80 items-center justify-center rounded-lg border border-gray-200 bg-white">
          <Spin description={`Загрузка карты: ${cityTrimmed}`} />
        </div>
      ) : (
        <RouteAnchorMapPicker
          center={mapCenter}
          value={mapValue}
          label={value?.label ?? ""}
          onGeocode={(query) => geocodeFn(query, cityTrimmed).then((data) => data.results)}
          onReverseGeocode={(lat, lon) =>
            reverseGeocodeFn(lat, lon, cityTrimmed).then((hit) => hit.label)
          }
          onChange={(point, meta) =>
            onChange({
              lat: point.lat,
              lon: point.lon,
              label: meta?.label?.trim() || "Базовая точка",
              source: meta?.source ?? "map",
              loop_end: loopEnd,
            })
          }
        />
      )}
      <Checkbox
        disabled={disabled}
        checked={loopEnd}
        onChange={(event) => {
          setLoopEnd(event.target.checked);
          if (value) {
            onChange({ ...value, loop_end: event.target.checked });
          }
        }}
      >
        Конечная точка совпадает с базовой
      </Checkbox>
      {value && (
        <Button
          type="link"
          danger
          disabled={disabled}
          className="!px-0"
          onClick={() => onChange(null)}
        >
          Убрать точку
        </Button>
      )}
    </div>
  );
}
