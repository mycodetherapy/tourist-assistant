import type { ItemVote } from "../api/types";
import type { TripRouteCase } from "../api/routeTypes";
import { ItemVoteButtons } from "./ItemVoteButtons";

function stripRouteParens(text: string): string {
  return text.replace(/\s*\([^)]*\)/g, "").trim();
}

export interface RouteStopVoteInfo {
  item_key: string;
  index: number;
  vote: ItemVote | null;
}

interface RouteCaseDetailsProps {
  routeCase: TripRouteCase;
  stopVotes?: Map<string, RouteStopVoteInfo>;
  onStopVote?: (poiId: string, itemKey: string, index: number, vote: ItemVote | null) => void;
  votingDisabled?: boolean;
}

export function RouteCaseDetails({
  routeCase,
  stopVotes,
  onStopVote,
  votingDisabled,
}: RouteCaseDetailsProps) {
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
        <ul className="my-1 list-none space-y-0.5 pl-0">
          {leisureStops.map((stop) => {
            const poiId = stop.poi_id ?? "";
            const voteInfo = poiId ? stopVotes?.get(poiId) : undefined;
            const canVote = Boolean(poiId && voteInfo && onStopVote);
            return (
              <li
                key={`${stop.order}-${poiId || stop.narrative}`}
                className="flex flex-wrap items-start gap-x-1 gap-y-0.5"
              >
                <span className="shrink-0 text-gray-400" aria-hidden>
                  •
                </span>
                <span className="min-w-0 flex-1">{stop.narrative}</span>
                {canVote ? (
                  <ItemVoteButtons
                    horizontal
                    vote={voteInfo!.vote}
                    disabled={votingDisabled}
                    onVote={(vote) =>
                      onStopVote!(poiId, voteInfo!.item_key, voteInfo!.index, vote)
                    }
                  />
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      <p className="mb-0 mt-1 text-xs text-gray-500">
        Рестораны — «Искать вдоль маршрута» в Яндекс.Картах.
      </p>
    </div>
  );
}
