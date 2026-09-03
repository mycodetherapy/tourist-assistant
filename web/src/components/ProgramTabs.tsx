import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Grid, Skeleton, notification } from "antd";
import { useCallback, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { getErrorMessage } from "../api/client";
import { submitItemFeedback } from "../api/trips";
import { guestSubmitItemFeedback } from "../api/guest";
import { parseRouteProgram, rawRouteCases, routeCaseAtIndex, routeMaterialsSummary } from "../api/routeTypes";
import type { ItemVote, ProgramResponse, VotableSectionKey } from "../api/types";
import { pickPreferredCaseId } from "../utils/routeVotes";
import { ItemVoteButtons } from "./ItemVoteButtons";
import { PoiFactModal } from "./PoiFactModal";
import { PoolSourceBanner } from "./PoolSourceBanner";
import { RouteCaseDetails } from "./RouteCaseDetails";
import { RouteCaseSwitcher } from "./RouteCaseSwitcher";
import { RouteMapView } from "./RouteMapView";
import { RoutePinButton } from "./RoutePinButton";
import { FREE_VS_LLM } from "../content/buildModes";
import { adjacentCaseId, useHorizontalSwipe, type SwipeDirection } from "../hooks/useHorizontalSwipe";
import { usePoiFact } from "../hooks/usePoiFact";
import { markdownExternalLinkComponents } from "./markdownExternalLink";

const { useBreakpoint } = Grid;

interface ProgramTabsProps {
  tripId: number;
  city: string;
  data: ProgramResponse;
  votingDisabled?: boolean;
  guestMode?: boolean;
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
      <ReactMarkdown components={markdownExternalLinkComponents}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function ProgramTabs({
  tripId,
  city,
  data,
  votingDisabled,
  guestMode = false,
}: ProgramTabsProps) {
  const queryClient = useQueryClient();
  const programQueryKey = guestMode
    ? (["guest", "trips", tripId, "program"] as const)
    : (["trips", tripId, "program"] as const);
  const screens = useBreakpoint();
  const isMobile = screens.md === false;
  const poiFact = usePoiFact(tripId, { guest: guestMode });
  const routeCases = parseRouteProgram(data.program.routes);
  const routeCasesRaw = rawRouteCases(data.program.routes);
  const defaultRouteCaseId = useMemo(
    () => pickPreferredCaseId(routeCasesRaw, data.sections.routes.items),
    [routeCasesRaw, data.sections.routes.items],
  );
  const [selectedRouteCaseId, setSelectedRouteCaseId] = useState<string | undefined>(
    defaultRouteCaseId,
  );
  const [swipeDir, setSwipeDir] = useState<SwipeDirection | null>(null);
  const activeRouteCaseId = selectedRouteCaseId ?? defaultRouteCaseId;
  const routeCaseIds = useMemo(
    () => routeCases.map((routeCase) => String(routeCase.case_id)),
    [routeCases],
  );
  const activeRouteCaseIdRef = useRef(activeRouteCaseId);
  activeRouteCaseIdRef.current = activeRouteCaseId;
  const swipeEnabled = isMobile && routeCaseIds.length > 1;

  const handleRouteCaseChange = useCallback((caseId: string) => {
    setSwipeDir(null);
    setSelectedRouteCaseId(caseId);
  }, []);

  const handleRouteCaseSwipe = useCallback(
    (direction: SwipeDirection) => {
      const nextId = adjacentCaseId(routeCaseIds, activeRouteCaseIdRef.current, direction);
      if (!nextId) {
        return;
      }
      setSwipeDir(direction);
      setSelectedRouteCaseId(nextId);
    },
    [routeCaseIds],
  );
  const swipeHandlers = useHorizontalSwipe(swipeEnabled, handleRouteCaseSwipe);
  const swipeInClass =
    swipeDir === "left"
      ? "route-case-swipe-in-left"
      : swipeDir === "right"
        ? "route-case-swipe-in-right"
        : "";
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
      section: VotableSectionKey;
      item_index: number;
      item_key: string;
      vote: ItemVote | null;
    }) =>
      guestMode
        ? guestSubmitItemFeedback(tripId, {
            version_id: data.version_id,
            section: payload.section,
            item_key: payload.item_key,
            item_index: payload.item_index,
            vote: payload.vote,
          })
        : submitItemFeedback(tripId, {
            version_id: data.version_id,
            section: payload.section,
            item_key: payload.item_key,
            item_index: payload.item_index,
            vote: payload.vote,
          }),
    onMutate: async (payload) => {
      await queryClient.cancelQueries({ queryKey: programQueryKey });
      const previous = queryClient.getQueryData<ProgramResponse>(programQueryKey);
      if (previous?.sections) {
        if (payload.section === "route_pins") {
          const section = previous.sections.routes;
          const updatedItems = section.items.map((item) =>
            item.item_key === payload.item_key || item.index === payload.item_index
              ? { ...item, pinned: payload.vote === 1 }
              : item,
          );
          queryClient.setQueryData<ProgramResponse>(programQueryKey, {
            ...previous,
            sections: {
              ...previous.sections,
              routes: { ...section, items: updatedItems },
            },
          });
        } else if (previous.sections[payload.section]) {
          const section = previous.sections[payload.section];
          const updatedItems = section.items.map((item) =>
            item.item_key === payload.item_key ? { ...item, vote: payload.vote } : item,
          );
          queryClient.setQueryData<ProgramResponse>(programQueryKey, {
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
      }
      return { previous };
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(programQueryKey, updated);
    },
    onError: (error, _payload, context) => {
      if (context?.previous) {
        queryClient.setQueryData(programQueryKey, context.previous);
      }
      notification.error({
        title: "Оценка не сохранена",
        description: getErrorMessage(error),
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: programQueryKey });
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
    section: VotableSectionKey,
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
      queryClient.invalidateQueries({ queryKey: programQueryKey });
      return;
    }
    voteMutation.mutate({ section, item_index: itemIndex, item_key: itemKey, vote });
  };

  const poolSummary =
    routeMaterialsSummary(data.program.routes) ??
    (data.sections.routes.intro.match(/^Пул:\s*\d+/i)
      ? data.sections.routes.intro.split("\n")[0]
      : null);
  const routesIntro = data.sections.routes.intro
    .replace(/^Пул:\s*\d+[^\n]*\n?/i, "")
    .trim();

  return (
    <div className="space-y-3">
      <PoolSourceBanner summary={poolSummary} />
      <p className="m-0 text-xs leading-relaxed text-slate-500">{FREE_VS_LLM.likesHint}</p>
      <div
        className={swipeEnabled ? "route-case-swipe flex flex-col gap-3" : "contents"}
        {...(swipeEnabled ? swipeHandlers : {})}
      >
        {isMobile && routeCases.length > 1 && (
          <RouteCaseSwitcher
            cases={routeCases}
            value={activeRouteCaseId ?? String(routeCases[0]?.case_id)}
            onChange={handleRouteCaseChange}
          />
        )}
        <MarkdownBlock text={routesIntro} />
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
              const routeCase = routeCaseAtIndex(routeCasesRaw, item.index);
              const useRouteCard =
                !!routeCase && Boolean(routeCase.maps_route_url || routeCase.stops.length);
              const hasMap = Boolean(
                routeCase?.maps_route_url || routeCase?.route_geometry?.coordinates?.length,
              );
              const detailsBlock = useRouteCard ? (
                <RouteCaseDetails
                  routeCase={routeCase}
                  stopVotes={stopVoteByPoi}
                  votingDisabled={votingDisabled || voteMutation.isPending}
                  onStopClick={(stop) => {
                    void poiFact.open(stop);
                  }}
                  onStopVote={(_poiId, itemKey, index, vote) =>
                    handleVote("route_stops", index, itemKey, vote)
                  }
                />
              ) : (
                <MarkdownBlock text={item.text} className="mb-0" />
              );
              const openStopFromMap = (stopIndex: number) => {
                if (!routeCase) {
                  return;
                }
                const leisure = routeCase.stops.filter((s) => s.kind === "leisure");
                const stop = leisure[stopIndex];
                if (!stop) {
                  return;
                }
                const name = (stop.narrative ?? "").trim() || "Место";
                void poiFact.open({ poiId: stop.poi_id ?? "", name });
              };
              const voteButtons = (
                <div
                  className={`flex shrink-0 gap-0.5 ${
                    isMobile ? "flex-row items-center self-end" : "flex-col items-center pt-0.5"
                  }`}
                >
                  <RoutePinButton
                    pinned={Boolean(item.pinned || routeCase?.preserved)}
                    horizontal={isMobile}
                    disabled={votingDisabled || voteMutation.isPending}
                    onToggle={(pinned) =>
                      handleVote("route_pins", item.index, item.item_key, pinned ? 1 : null)
                    }
                  />
                  <ItemVoteButtons
                    vote={item.vote}
                    horizontal={isMobile}
                    disabled={votingDisabled || voteMutation.isPending}
                    onVote={(vote) => handleVote("routes", item.index, item.item_key, vote)}
                  />
                </div>
              );
              if (isMobile && hasMap) {
                return (
                  <li
                    key={`routes-${item.item_key}`}
                    className={`route-item--with-map flex flex-col rounded-lg border border-gray-100 bg-white ${swipeInClass}`.trim()}
                  >
                    <RouteMapView
                      routeCase={routeCase!}
                      city={city}
                      onStopClick={(stopIndex) => openStopFromMap(stopIndex)}
                    />
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
                  } ${isMobile ? swipeInClass : ""}`.trim()}
                >
                  <div className="min-w-0 flex-1">
                    {hasMap && routeCase ? (
                      <RouteMapView
                        routeCase={routeCase}
                        city={city}
                        onStopClick={(stopIndex) => openStopFromMap(stopIndex)}
                      />
                    ) : null}
                    {detailsBlock}
                  </div>
                  {voteButtons}
                </li>
              );
            })}
        </ul>
        )}
      </div>

      <div className="rounded-lg border border-gray-100 bg-white px-3 py-3">
        <h3 className="mb-2 text-sm font-semibold text-gray-700">О городе</h3>
        {data.city_fact_status === "pending" ? (
          <Skeleton active paragraph={{ rows: 3 }} title={false} />
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

      <PoiFactModal
        open={poiFact.isOpen}
        title={poiFact.target?.name ?? "Место"}
        loading={poiFact.loading}
        error={poiFact.error}
        data={poiFact.data}
        onClose={poiFact.close}
      />
    </div>
  );
}
