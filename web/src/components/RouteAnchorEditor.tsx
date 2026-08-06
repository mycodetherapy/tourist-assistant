import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Checkbox, notification } from "antd";
import { useEffect, useMemo, useState } from "react";
import { getErrorMessage } from "../api/client";
import {
  fetchCityCenter,
  fetchPreferences,
  geocodeAddress,
  reverseGeocodeAddress,
  updatePreferences,
} from "../api/trips";
import {
  guestFetchCityCenter,
  guestFetchPreferences,
  guestGeocodeAddress,
  guestReverseGeocodeAddress,
  guestUpdatePreferences,
} from "../api/guest";
import type { TripRouteCase } from "../api/routeTypes";
import type { RouteAnchor } from "../api/types";
import { parseMapsRoutePoints } from "../utils/mapsRoutePoints";
import { RouteAnchorMapPicker, type MapPoint } from "./RouteAnchorMapPicker";

interface RouteAnchorEditorProps {
  tripId: number;
  city: string;
  routeCases?: TripRouteCase[];
  guestMode?: boolean;
  onSaved?: () => void;
}

function emptyDraft(): Partial<RouteAnchor> {
  return { label: "", loop_end: false };
}

export function RouteAnchorEditor({
  tripId,
  city,
  routeCases = [],
  guestMode = false,
  onSaved,
}: RouteAnchorEditorProps) {
  const queryClient = useQueryClient();
  const queryPrefix = guestMode ? "guest" : "trips";
  const prefsQuery = useQuery({
    queryKey: [queryPrefix, tripId, "preferences"],
    queryFn: () =>
      guestMode ? guestFetchPreferences(tripId) : fetchPreferences(tripId),
  });
  const cityCenterQuery = useQuery({
    queryKey: [queryPrefix, tripId, "city-center"],
    queryFn: () =>
      guestMode ? guestFetchCityCenter(tripId) : fetchCityCenter(tripId),
  });

  const [draft, setDraft] = useState<Partial<RouteAnchor>>(emptyDraft());
  const [bannerKind, setBannerKind] = useState<"saved" | "deleted" | null>(null);

  const savedAnchor = prefsQuery.data?.route_anchor ?? null;
  const hasPoint = draft.lat != null && draft.lon != null;

  useEffect(() => {
    if (savedAnchor) {
      setDraft({
        lat: savedAnchor.lat,
        lon: savedAnchor.lon,
        label: savedAnchor.label,
        source: savedAnchor.source,
        loop_end: savedAnchor.loop_end,
      });
    } else {
      setDraft(emptyDraft());
    }
    setBannerKind(null);
  }, [savedAnchor?.lat, savedAnchor?.lon, savedAnchor?.label, savedAnchor?.loop_end]);

  const routeMapCenter = useMemo((): MapPoint | null => {
    const preferred = routeCases.find((c) => c.maps_route_url)?.maps_route_url;
    if (!preferred) {
      return null;
    }
    const points = parseMapsRoutePoints(preferred);
    if (points.length === 0) {
      return null;
    }
    return points[0];
  }, [routeCases]);

  const mapInitialCenter: MapPoint = useMemo(() => {
    if (routeMapCenter) {
      return routeMapCenter;
    }
    if (cityCenterQuery.data) {
      return { lat: cityCenterQuery.data.lat, lon: cityCenterQuery.data.lon };
    }
    return { lat: 55.75, lon: 37.62 };
  }, [routeMapCenter, cityCenterQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (anchor: RouteAnchor | null) =>
      guestMode
        ? guestUpdatePreferences(tripId, { route_anchor: anchor })
        : updatePreferences(tripId, { route_anchor: anchor }),
    onSuccess: (_data, anchor) => {
      queryClient.invalidateQueries({ queryKey: [queryPrefix, tripId, "preferences"] });
      const deleted = anchor === null;
      setBannerKind(deleted ? "deleted" : "saved");
      onSaved?.();
      notification.success({
        title: deleted ? "Базовая точка удалена" : "Базовая точка сохранена",
      });
    },
    onError: (error) => {
      notification.error({ title: "Не сохранено", description: getErrorMessage(error) });
    },
  });

  const handleSave = () => {
    if (draft.lat == null || draft.lon == null) {
      notification.warning({ title: "Укажите точку на карте или через поиск" });
      return;
    }
    const anchor: RouteAnchor = {
      lat: draft.lat,
      lon: draft.lon,
      label: (draft.label ?? "").trim(),
      source: draft.source ?? "map",
      loop_end: Boolean(draft.loop_end),
    };
    saveMutation.mutate(anchor);
  };

  const handleDelete = () => {
    saveMutation.mutate(null);
    setDraft(emptyDraft());
  };

  const mapPickerValue =
    draft.lat != null && draft.lon != null ? { lat: draft.lat, lon: draft.lon } : null;

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-600">
        Базовая точка — отель, квартира или вокзал. Найдите адрес в поле над картой, введите
        координаты (56.85, 35.88) или кликните на карту. После изменения нажмите «Пересобрать» с
        областью «Маршруты».
      </p>

      {bannerKind === "saved" && (
        <Alert
          type="info"
          showIcon
          title="Точка сохранена"
          description="Пересоберите раздел «Маршруты», чтобы обновить ссылки на Яндекс.Карты."
        />
      )}
      {bannerKind === "deleted" && (
        <Alert
          type="success"
          showIcon
          title="Базовая точка удалена"
          description="Пересоберите раздел «Маршруты», чтобы убрать базовую точку из ссылок на карту."
        />
      )}

      <RouteAnchorMapPicker
        center={mapInitialCenter}
        value={mapPickerValue}
        label={draft.label ?? ""}
        onGeocode={(query) =>
          (guestMode
            ? guestGeocodeAddress(tripId, query, city)
            : geocodeAddress(tripId, query, city)
          ).then((data) => data.results)
        }
        onReverseGeocode={(lat, lon) =>
          (guestMode
            ? guestReverseGeocodeAddress(tripId, lat, lon, city)
            : reverseGeocodeAddress(tripId, lat, lon, city)
          ).then((hit) => hit.label)
        }
        onChange={(point, meta) =>
          setDraft((prev) => ({
            ...prev,
            lat: point.lat,
            lon: point.lon,
            label: meta?.label ?? "",
            source: meta?.source ?? "map",
          }))
        }
        hint="Адрес, объект или координаты — поле над картой; также можно кликнуть на карту"
      />

      <div className="mt-4 space-y-3">
        <Checkbox
          checked={Boolean(draft.loop_end)}
          disabled={!hasPoint}
          onChange={(event) =>
            setDraft((prev) => ({ ...prev, loop_end: event.target.checked }))
          }
        >
          Конечная точка совпадает с базовой (кольцевой маршрут)
        </Checkbox>

        <div className="h-11 overflow-hidden text-xs leading-5 text-gray-500">
          {hasPoint ? (
            <span className="line-clamp-2 block">
              {draft.label?.trim() || "Без названия"} — {draft.lat!.toFixed(5)}, {draft.lon!.toFixed(5)}
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-3">
          <Button
            type="primary"
            loading={saveMutation.isPending}
            disabled={!hasPoint}
            onClick={handleSave}
          >
            Сохранить
          </Button>
          {savedAnchor && (
            <Button danger loading={saveMutation.isPending} onClick={handleDelete}>
              Удалить точку
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
