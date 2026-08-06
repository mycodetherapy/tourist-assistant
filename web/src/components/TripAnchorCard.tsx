import { useQuery } from "@tanstack/react-query";
import { Collapse } from "antd";
import { useMemo, useState } from "react";
import { fetchPreferences } from "../api/trips";
import { guestFetchPreferences } from "../api/guest";
import type { TripRouteCase } from "../api/routeTypes";
import type { RouteAnchor } from "../api/types";
import { RouteAnchorEditor } from "./RouteAnchorEditor";

interface TripAnchorCardProps {
  tripId: number;
  city: string;
  routeCases?: TripRouteCase[];
  guestMode?: boolean;
}

const PANEL_KEY = "route-anchor";

function anchorPanelLabel(anchor: RouteAnchor | null | undefined): string {
  if (!anchor) {
    return "Базовая точка не задана";
  }
  const label = anchor.label?.trim();
  if (label) {
    return `Старт: ${label}`;
  }
  return `Старт: ${anchor.lat.toFixed(5)}, ${anchor.lon.toFixed(5)}`;
}

export function TripAnchorCard({ tripId, city, routeCases, guestMode = false }: TripAnchorCardProps) {
  const [activeKeys, setActiveKeys] = useState<string[]>([]);
  const prefsQuery = useQuery({
    queryKey: [guestMode ? "guest" : "trips", tripId, "preferences"],
    queryFn: () =>
      guestMode ? guestFetchPreferences(tripId) : fetchPreferences(tripId),
  });

  const panelLabel = useMemo(
    () => anchorPanelLabel(prefsQuery.data?.route_anchor),
    [prefsQuery.data?.route_anchor],
  );

  return (
    <Collapse
      className="trip-anchor-collapse"
      activeKey={activeKeys}
      onChange={(keys) => setActiveKeys(Array.isArray(keys) ? keys : [keys])}
      items={[
        {
          key: PANEL_KEY,
          label: (
            <span className="trip-anchor-collapse-label line-clamp-2 text-sm font-medium">
              {panelLabel}
            </span>
          ),
          children: (
            <RouteAnchorEditor
              tripId={tripId}
              city={city}
              routeCases={routeCases}
              guestMode={guestMode}
              onSaved={() => setActiveKeys([])}
            />
          ),
        },
      ]}
    />
  );
}
