import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Grid, Skeleton, notification } from "antd";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { getErrorMessage } from "../api/client";
import { submitItemFeedback } from "../api/trips";
import { parseRouteProgram, rawRouteCases, routeCaseAtIndex } from "../api/routeTypes";
import type { ItemVote, ProgramResponse } from "../api/types";
import { pickPreferredCaseId } from "../utils/routeVotes";
import { ItemVoteButtons } from "./ItemVoteButtons";
import { RouteCaseDetails } from "./RouteCaseDetails";
import { RouteCaseSwitcher } from "./RouteCaseSwitcher";
import { RouteMapView } from "./RouteMapView";

const { useBreakpoint } = Grid;

interface ProgramTabsProps {
  tripId: number;
  city: string;
  data: ProgramResponse;
  votingDisabled?: boolean;
}

function MarkdownBlock({
  text,
  className = "mb-4",
  compact = false,
}: {
  text: string;
  className?: string;
  compact?: boolean;
}) {
  if (!text.trim()) {
    return null;
  }

  return (
    <div
      className={`prose max-w-none ${compact ? "" : "whitespace-pre-wrap"} ${className}`}
    >
      <ReactMarkdown>
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function ProgramTabs({ tripId, city, data, votingDisabled }: ProgramTabsProps) {
  const queryClient = useQueryClient();
  const screens = useBreakpoint();
  const isMobile = screens.md === false;
  const routeCases = parseRouteProgram(data.program.routes);
  const routeCasesRaw = rawRouteCases(data.program.routes);
  const defaultRouteCaseId = useMemo(
    () => pickPreferredCaseId(routeCasesRaw, data.sections.routes.items),
    [routeCasesRaw, data.sections.routes.items],
  );
  const [selectedRouteCaseId, setSelectedRouteCaseId] = useState<string | undefined>(
    defaultRouteCaseId,
  );
  const activeRouteCaseId = selectedRouteCaseId ?? defaultRouteCaseId;
  const stopVoteByPoi = new Map(
    (data.sections.route_stops?.items ?? [])
      .filter((item) => item.poi_id)
      .map((item) => [
        item.poi_id as string,
        { item_key: item.item_key, index: item.index, vote: item.vote },
      ]),
  );

  const voteMutation = useMutation({
    mutationFn: (payload: {
      section: "routes" | "route_stops";
      item_index: number;
      item_key: string;
      vote: ItemVote | null;
    }) =>
      submitItemFeedback(tripId, {
        version_id: data.version_id,
        section: payload.section,
        item_key: payload.item_key,
        item_index: payload.item_index,
        vote: payload.vote,
      }),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey: ["trips", tripId, "program"] });
      const previous = queryClient.getQueryData<ProgramResponse>([
        "trips",
        tripId,
        "program",
      ]);
      if (previous?.sections?.[payload.section]) {
        const section = previous.sections[payload.section];
        const updatedItems = section.items.map((item) =>
          item.item_key === payload.item_key ? { ...item, vote: payload.vote } : item,
        );
        queryClient.setQueryData<ProgramResponse>(["trips", tripId, "program"], {
          ...previous,
          sections: {
            ...previous.sections,
            [payload.section]: {
              ...section,
              items: updatedItems,
            },
          },
        });
      }
      return { previous };
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["trips", tripId, "program"], updated);
    },
    onError: (error, _payload, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["trips", tripId, "program"], context.previous);
      }
      notification.error({
        title: "Оценка не сохранена",
        description: getErrorMessage(error),
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["trips", tripId, "program"] });
    },
  });

  if (!data.sections) {
    return (
      <Alert
        type="warning"
        showIcon
        title="Не удалось загрузить пункты программы"
        description="Перезапустите API (uvicorn или docker compose build api && docker compose up api)."
      />
    );
  }

  const handleVote = (
    section: "routes" | "route_stops",
    itemIndex: number,
    itemKey: string | undefined,
    vote: ItemVote | null,
  ) => {
    if (votingDisabled || voteMutation.isPending) {
      return;
    }
    if (!itemKey) {
      notification.error({
        title: "Оценка не сохранена",
        description: "Обновите страницу (Ctrl+Shift+R) и попробуйте снова.",
      });
      queryClient.invalidateQueries({ queryKey: ["trips", tripId, "program"] });
      return;
    }
    voteMutation.mutate({ section, item_index: itemIndex, item_key: itemKey, vote });
  };

  return (
    <div className="space-y-3">
      {isMobile && routeCases.length > 1 && (
        <RouteCaseSwitcher
          cases={routeCases}
          value={activeRouteCaseId ?? String(routeCases[0]?.case_id)}
          onChange={setSelectedRouteCaseId}
        />
      )}
      <MarkdownBlock text={data.sections.routes.intro} />
      {data.sections.routes.items.length === 0 && data.program.routes_text?.trim() ? (
        <MarkdownBlock text={data.program.routes_text} />
      ) : (
        <ul className="space-y-2">
          {data.sections.routes.items
            .filter((item) => {
              if (!isMobile || !activeRouteCaseId) {
                return true;
              }
              const routeCase = routeCaseAtIndex(routeCasesRaw, item.index);
              return routeCase && String(routeCase.case_id) === activeRouteCaseId;
            })
            .map((item) => {
              const routeCase = routeCaseAtIndex(routeCases, item.index);
              const useRouteCard =
                !!routeCase && Boolean(routeCase.maps_route_url || routeCase.stops.length);
              const hasMap = Boolean(routeCase?.maps_route_url);
              const detailsBlock = useRouteCard ? (
                <RouteCaseDetails
                  routeCase={routeCase}
                  stopVotes={stopVoteByPoi}
                  votingDisabled={votingDisabled || voteMutation.isPending}
                  onStopVote={(_poiId, itemKey, index, vote) =>
                    handleVote("route_stops", index, itemKey, vote)
                  }
                />
              ) : (
                <MarkdownBlock text={item.text} className="mb-0" />
              );
              const voteButtons = (
                <ItemVoteButtons
                  vote={item.vote}
                  horizontal={isMobile}
                  className={isMobile ? "self-end" : undefined}
                  disabled={votingDisabled || voteMutation.isPending}
                  onVote={(vote) => handleVote("routes", item.index, item.item_key, vote)}
                />
              );
              if (isMobile && hasMap) {
                return (
                  <li
                    key={`routes-${item.item_key}`}
                    className="route-item--with-map flex flex-col rounded-lg border border-gray-100 bg-white"
                  >
                    <RouteMapView routeCase={routeCase!} city={city} />
                    <div className="route-item-body flex flex-col gap-2">
                      <div className="min-w-0 flex-1">{detailsBlock}</div>
                      {voteButtons}
                    </div>
                  </li>
                );
              }
              return (
                <li
                  key={`routes-${item.item_key}`}
                  className={`flex items-start gap-2 rounded-lg border border-gray-100 bg-white px-2.5 py-2 ${
                    isMobile ? "flex-col" : ""
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    {routeCase?.maps_route_url ? (
                      <RouteMapView routeCase={routeCase} city={city} />
                    ) : null}
                    {detailsBlock}
                  </div>
                  {voteButtons}
                </li>
              );
            })}
        </ul>
      )}

      <div className="rounded-lg border border-gray-100 bg-white px-3 py-3">
        <h3 className="mb-2 text-sm font-semibold text-gray-700">О городе</h3>
        {data.city_fact_status === "pending" ? (
          <Skeleton active paragraph={{ rows: 2 }} title={false} />
        ) : data.city_fact_status === "failed" ? (
          <Alert
            type="info"
            showIcon
            className="mb-0"
            title="Факт о городе временно недоступен"
          />
        ) : (
          <MarkdownBlock
            text={data.program.lifehacks || data.sections.lifehacks.intro}
            className="mb-0"
          />
        )}
      </div>
    </div>
  );
}
