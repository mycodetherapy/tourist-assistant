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

export interface RouteStopClickInfo {
  poiId: string;
  name: string;
}

interface RouteCaseDetailsProps {
  routeCase: TripRouteCase;
  stopVotes?: Map<string, RouteStopVoteInfo>;
  onStopVote?: (poiId: string, itemKey: string, index: number, vote: ItemVote | null) => void;
  onStopClick?: (stop: RouteStopClickInfo) => void;
  votingDisabled?: boolean;
}

export function RouteCaseDetails({
  routeCase,
  stopVotes,
  onStopVote,
  onStopClick,
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
      {leisureStops.length > 0 ? (
        <ul className="my-1 list-none space-y-0.5 pl-0">
          {leisureStops.map((stop) => {
            const poiId = stop.poi_id ?? "";
            const label = (stop.narrative ?? "").trim() || "Место";
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
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left text-gray-800 underline-offset-2 hover:text-blue-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                  onClick={() => onStopClick?.({ poiId, name: label })}
                >
                  {label}
                </button>
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
    </div>
  );
}
