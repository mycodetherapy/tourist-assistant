import type { TripRouteCase } from "../api/routeTypes";

function stripRouteParens(text: string): string {
  return text.replace(/\s*\([^)]*\)/g, "").trim();
}

interface RouteCaseDetailsProps {
  routeCase: TripRouteCase;
}

export function RouteCaseDetails({ routeCase }: RouteCaseDetailsProps) {
  const leisureStops = routeCase.stops.filter((stop) => stop.kind === "leisure");

  return (
    <div className="route-case-details text-sm leading-snug text-gray-800">
      <h4 className="m-0 text-[15px] font-semibold text-gray-900">
        Вариант {routeCase.case_id}: {stripRouteParens(routeCase.title)}
      </h4>
      {leisureStops.length > 0 ? (
        <p className="my-0.5 text-gray-600">{leisureStops.length} остановок</p>
      ) : null}
      {routeCase.maps_route_url ? (
        <p className="my-1">
          <a
            href={routeCase.maps_route_url}
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 underline"
          >
            Открыть маршрут в Яндекс.Картах
          </a>
        </p>
      ) : null}
      {leisureStops.length > 0 ? (
        <ul className="my-1 list-inside list-disc space-y-0 pl-0.5">
          {leisureStops.map((stop) => (
            <li key={`${stop.order}-${stop.poi_id ?? stop.narrative}`} className="marker:text-gray-400">
              {stop.narrative}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mb-0 mt-1 text-xs text-gray-500">
        Рестораны — «Искать вдоль маршрута» в Яндекс.Картах.
      </p>
    </div>
  );
}
