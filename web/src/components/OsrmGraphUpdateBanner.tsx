import { useQuery } from "@tanstack/react-query";
import { Alert, Button } from "antd";
import { fetchTripOsrmUpdate } from "../api/trips";

interface OsrmGraphUpdateBannerProps {
  tripId: number;
  /** Есть собранные маршруты (иначе баннер не нужен). */
  hasRoutes: boolean;
  rebuilding?: boolean;
  onRebuildRoutes: () => void;
}

/** Баннер: граф OSRM города обновился после последней сборки маршрутов. */
export function OsrmGraphUpdateBanner({
  tripId,
  hasRoutes,
  rebuilding,
  onRebuildRoutes,
}: OsrmGraphUpdateBannerProps) {
  const query = useQuery({
    queryKey: ["trip-osrm-update", tripId],
    queryFn: () => fetchTripOsrmUpdate(tripId),
    enabled: hasRoutes && Number.isFinite(tripId) && tripId > 0,
    staleTime: 60_000,
  });

  if (!hasRoutes || !query.data?.update_available) {
    return null;
  }

  const city = query.data.display_name || query.data.slug || "города";

  return (
    <Alert
      className="mb-4"
      type="info"
      showIcon
      title="Карта города обновилась"
      description={
        <div className="space-y-2">
          <p className="m-0">
            Пеший граф для «{city}» стал новее ваших маршрутов. Пересоберите маршруты,
            чтобы линия на карте совпала с актуальными дорогами.
          </p>
          <Button
            type="primary"
            size="small"
            loading={rebuilding}
            onClick={onRebuildRoutes}
          >
            Пересобрать маршруты
          </Button>
        </div>
      }
    />
  );
}
