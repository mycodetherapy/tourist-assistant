import { useQuery } from "@tanstack/react-query";
import { Alert } from "antd";
import { fetchPreferences } from "../api/trips";

interface RouteAnchorSummaryProps {
  tripId: number;
}

/** Краткий статус базовой точки на вкладке «Маршруты». */
export function RouteAnchorSummary({ tripId }: RouteAnchorSummaryProps) {
  const prefsQuery = useQuery({
    queryKey: ["trips", tripId, "preferences"],
    queryFn: () => fetchPreferences(tripId),
  });
  const anchor = prefsQuery.data?.route_anchor;

  if (!anchor) {
    return (
      <Alert
        type="info"
        showIcon
        className="mb-3"
        message="Базовая точка не задана"
        description="Укажите отель или место проживания в настройках поездки ниже — маршруты начнутся от неё после пересборки."
      />
    );
  }

  const label = anchor.label?.trim() || "Базовая точка";
  const loopNote = anchor.loop_end ? " · возврат в точку старта" : "";

  return (
    <Alert
      type="success"
      showIcon
      className="mb-3"
      message={`Старт маршрута: ${label}${loopNote}`}
      description={`${anchor.lat.toFixed(5)}, ${anchor.lon.toFixed(5)}. Изменили точку? Пересоберите раздел «Маршруты».`}
    />
  );
}
