import { Collapse } from "antd";
import { useState } from "react";
import type { TripRouteCase } from "../api/routeTypes";
import { RouteAnchorEditor } from "./RouteAnchorEditor";

interface TripAnchorCardProps {
  tripId: number;
  city: string;
  routeCases?: TripRouteCase[];
}

const PANEL_KEY = "route-anchor";

export function TripAnchorCard({ tripId, city, routeCases }: TripAnchorCardProps) {
  const [activeKeys, setActiveKeys] = useState<string[]>([]);

  return (
    <Collapse
      className="trip-anchor-collapse"
      activeKey={activeKeys}
      onChange={(keys) => setActiveKeys(Array.isArray(keys) ? keys : [keys])}
      items={[
        {
          key: PANEL_KEY,
          label: "Базовая точка маршрута",
          children: (
            <RouteAnchorEditor
              tripId={tripId}
              city={city}
              routeCases={routeCases}
              onSaved={() => setActiveKeys([])}
            />
          ),
        },
      ]}
    />
  );
}
