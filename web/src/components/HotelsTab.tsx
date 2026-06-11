import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Segmented, Spin } from "antd";
import { useMemo, useState } from "react";
import { getErrorMessage } from "../api/client";
import type { TripRouteCase } from "../api/routeTypes";
import { fetchHotelZones, logAffiliateClick } from "../api/trips";
import type { ProgramItem } from "../api/types";
import { pickPreferredCaseId } from "../utils/routeVotes";
import { RouteMapEmbed } from "./RouteMapEmbed";

interface HotelsTabProps {
  tripId: number;
  /** Порядок как в API (голоса). */
  routeCasesForVotes: TripRouteCase[];
  /** Отсортированные A/B/C для UI. */
  routeCasesDisplay: TripRouteCase[];
  routeItems: ProgramItem[];
}

const WIDGET_HTML = import.meta.env.VITE_TP_BOOKING_WIDGET_HTML?.trim() ?? "";

export function HotelsTab({
  tripId,
  routeCasesForVotes,
  routeCasesDisplay,
  routeItems,
}: HotelsTabProps) {
  const defaultCaseId = useMemo(
    () => pickPreferredCaseId(routeCasesForVotes, routeItems),
    [routeCasesForVotes, routeItems],
  );
  const [selectedCaseId, setSelectedCaseId] = useState<string | undefined>(defaultCaseId);

  const zonesQuery = useQuery({
    queryKey: ["trips", tripId, "hotel-zones", selectedCaseId ?? "auto"],
    queryFn: () => fetchHotelZones(tripId, selectedCaseId),
    enabled: routeCasesForVotes.length > 0,
  });

  const activeCaseId = zonesQuery.data?.case_id ?? selectedCaseId ?? defaultCaseId;
  const activeCase =
    routeCasesDisplay.find((c) => String(c.case_id) === activeCaseId) ??
    routeCasesForVotes.find((c) => String(c.case_id) === activeCaseId) ??
    routeCasesDisplay[0];

  const handleBookingClick = (url: string) => {
    void logAffiliateClick(tripId, url).catch(() => undefined);
  };

  if (routeCasesForVotes.length === 0) {
    return (
      <Alert
        type="info"
        showIcon
        message="Нет маршрутов"
        description="Сначала сгенерируйте программу с маршрутами A / B / C."
      />
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">
        Отели подбираются вдоль выбранного маршрута. Ссылки ведут на Booking.com (партнёрская
        программа Travelpayouts).
      </p>

      <div>
        <p className="mb-2 text-sm font-medium text-gray-700">Маршрут</p>
        <Segmented
          className="hotels-route-select"
          value={activeCaseId}
          onChange={(value) => setSelectedCaseId(String(value))}
          options={routeCasesDisplay.map((routeCase) => ({
            label: `Вариант ${routeCase.case_id}`,
            value: String(routeCase.case_id),
          }))}
        />
      </div>

      {activeCase?.maps_route_url ? (
        <RouteMapEmbed
          mapsRouteUrl={activeCase.maps_route_url}
          caseId={String(activeCase.case_id)}
          title={activeCase.title}
        />
      ) : (
        <Alert
          type="warning"
          showIcon
          message="Карта маршрута недоступна"
          description="У этого варианта нет ссылки на Яндекс.Карты — зоны поиска могут быть недоступны."
        />
      )}

      {zonesQuery.isLoading ? (
        <div className="flex justify-center py-6">
          <Spin />
        </div>
      ) : zonesQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="Не удалось загрузить зоны отелей"
          description={getErrorMessage(zonesQuery.error)}
        />
      ) : zonesQuery.data && zonesQuery.data.zones.length === 0 ? (
        <Alert
          type="info"
          showIcon
          message="Нет зон поиска"
          description="Для маршрута не найдены координаты. Пересоберите маршруты или проверьте maps_route_url."
        />
      ) : zonesQuery.data ? (
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-700">Отели вдоль маршрута</p>
          <ul className="space-y-2">
            {zonesQuery.data.zones.map((zone) => (
              <li key={zone.zone_id}>
                <Card size="small" className="border-gray-100">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{zone.label}</p>
                      {zonesQuery.data?.checkin && zonesQuery.data?.checkout ? (
                        <p className="text-xs text-gray-500">
                          {zonesQuery.data.checkin} — {zonesQuery.data.checkout},{" "}
                          {zonesQuery.data.guests_adults} гост.
                        </p>
                      ) : null}
                    </div>
                    <Button
                      type="primary"
                      href={zone.booking_url}
                      target="_blank"
                      rel="noreferrer"
                      onClick={() => handleBookingClick(zone.booking_url)}
                    >
                      Искать на Booking
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {WIDGET_HTML ? (
        <div
          className="booking-widget-embed overflow-hidden rounded-lg border border-gray-200"
          dangerouslySetInnerHTML={{ __html: WIDGET_HTML }}
        />
      ) : (
        <Alert
          type="info"
          showIcon
          message="Виджет Travelpayouts"
          description={
            <>
              Подключите программу Booking.com в кабинете Travelpayouts → Tools → Widget. Скопируйте
              embed-код в переменную <code>VITE_TP_BOOKING_WIDGET_HTML</code> в{" "}
              <code>web/.env</code> и перезапустите <code>npm run dev</code>.
            </>
          }
        />
      )}
    </div>
  );
}
