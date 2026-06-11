import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Grid, Tabs, notification } from "antd";
import ReactMarkdown from "react-markdown";
import { getErrorMessage } from "../api/client";
import { submitItemFeedback } from "../api/trips";
import { parseRouteProgram, routeCaseAtIndex } from "../api/routeTypes";
import type { ItemVote, ProgramResponse, VotableSectionKey } from "../api/types";
import { normalizeTicketsMarkdown } from "../utils/ticketsMarkdown";
import { ItemVoteButtons } from "./ItemVoteButtons";
import { RouteCaseDetails } from "./RouteCaseDetails";
import { RouteMapEmbed } from "./RouteMapEmbed";

const { useBreakpoint } = Grid;

interface ProgramTabsProps {
  tripId: number;
  data: ProgramResponse;
  votingDisabled?: boolean;
}

type TabKey = "tickets" | VotableSectionKey;

interface TabDef {
  key: TabKey;
  label: string;
  votable: boolean;
}

function routeCaseCount(program: ProgramResponse["program"]): number {
  return parseRouteProgram(program.routes).length;
}

function hasRoutesProgram(program: ProgramResponse["program"]): boolean {
  return routeCaseCount(program) > 0 || Boolean(program.routes_text?.trim());
}

function isLegacyProgram(data: ProgramResponse): boolean {
  const { program } = data;
  const hasLegacy = Boolean(program.events?.trim() || program.dining?.trim());
  return hasLegacy && !hasRoutesProgram(program);
}

function buildTabs(data: ProgramResponse): TabDef[] {
  if (isLegacyProgram(data)) {
    return [
      { key: "tickets", label: "Билеты", votable: false },
      { key: "events", label: "Мероприятия", votable: true },
      { key: "dining", label: "Питание", votable: true },
      { key: "lifehacks", label: "Лайфхаки", votable: true },
    ];
  }
  const count = routeCaseCount(data.program);
  const routesLabel = count > 0 ? `Маршруты (${count})` : "Маршруты";
  return [
    { key: "tickets", label: "Билеты", votable: false },
    { key: "routes", label: routesLabel, votable: true },
    { key: "lifehacks", label: "Лайфхаки", votable: true },
  ];
}

function MarkdownBlock({
  text,
  className = "mb-4",
  compact = false,
  tripId,
  trackAffiliateClicks = false,
}: {
  text: string;
  className?: string;
  compact?: boolean;
  tripId?: number;
  trackAffiliateClicks?: boolean;
}) {
  if (!text.trim()) {
    return null;
  }

  const handleTicketLinkClick = (href: string | undefined) => {
    if (!trackAffiliateClicks || !tripId || !href) {
      return;
    }
    void import("../api/trips").then(({ logAffiliateClick }) =>
      logAffiliateClick(tripId, href).catch(() => undefined),
    );
  };

  return (
    <div
      className={`prose max-w-none ${compact ? "prose-tickets" : "whitespace-pre-wrap"} ${className}`}
    >
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 underline"
              onClick={() => handleTicketLinkClick(href)}
            >
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function ProgramTabs({ tripId, data, votingDisabled }: ProgramTabsProps) {
  const queryClient = useQueryClient();
  const screens = useBreakpoint();
  const isMobile = screens.md === false;
  const tabs = buildTabs(data);
  const legacy = isLegacyProgram(data);
  const routeCases = parseRouteProgram(data.program.routes);
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
        message: "Оценка не сохранена",
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
        message="Не удалось загрузить пункты программы"
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
        message: "Оценка не сохранена",
        description: "Обновите страницу (Ctrl+Shift+R) и попробуйте снова.",
      });
      queryClient.invalidateQueries({ queryKey: ["trips", tripId, "program"] });
      return;
    }
    voteMutation.mutate({ section, item_index: itemIndex, item_key: itemKey, vote });
  };

  return (
    <div className="space-y-3">
      {!legacy && hasRoutesProgram(data.program) && (
        <Alert
          type={
            (data.program.routes_text || "").includes("(fallback)") ? "warning" : "success"
          }
          showIcon
          message="Три варианта маршрута на всю поездку"
          description={
            (data.program.routes_text || "").includes("(fallback)")
              ? "Использованы демо-точки: проверьте доступ к Wikidata/Nominatim. python3 scripts/test_yandex_maps.py Город"
              : "Оцените варианты A / B / C. Карта встроена в каждый вариант; ссылка на Яндекс.Карты — в описании."
          }
        />
      )}
      <Tabs
        className="program-tabs"
        size="small"
        items={tabs.map(({ key, label, votable }) => {
          if (!votable) {
            return {
              key,
              label,
              children: (
                <>
                  <p className="mb-3 text-xs text-gray-500">
                    Ссылки на агрегаторы билетов партнёрские: при покупке сервис может получить
                    вознаграждение.
                  </p>
                  <MarkdownBlock
                    text={normalizeTicketsMarkdown(data.program.tickets)}
                    compact
                    tripId={tripId}
                    trackAffiliateClicks
                  />
                </>
              ),
            };
          }

          const sectionKey = key as VotableSectionKey;
          const section = data.sections[sectionKey];
          const routesFallback =
            sectionKey === "routes" &&
            section.items.length === 0 &&
            data.program.routes_text?.trim()
              ? data.program.routes_text
              : "";

          return {
            key,
            label,
            children: (
              <div>
                <MarkdownBlock text={section.intro} />
                {section.items.length === 0 && routesFallback ? (
                  <MarkdownBlock text={routesFallback} />
                ) : section.items.length === 0 ? (
                  <p className="text-gray-500">Нет пунктов в этой секции.</p>
                ) : (
                  <ul className="space-y-2">
                    {section.items.map((item) => {
                      const routeCase =
                        sectionKey === "routes"
                          ? routeCaseAtIndex(routeCases, item.index)
                          : undefined;
                      const useRouteCard =
                        sectionKey === "routes" &&
                        routeCase &&
                        Boolean(routeCase.maps_route_url || routeCase.stops.length);
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
                          onVote={(vote) =>
                            handleVote(sectionKey, item.index, item.item_key, vote)
                          }
                        />
                      );

                      if (isMobile && hasMap) {
                        return (
                          <li
                            key={`${sectionKey}-${item.item_key}`}
                            className="route-item--with-map flex flex-col overflow-visible rounded-lg border border-gray-100 bg-white"
                          >
                            <RouteMapEmbed
                              mapsRouteUrl={routeCase!.maps_route_url}
                              caseId={routeCase!.case_id}
                              title={routeCase!.title}
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
                          key={`${sectionKey}-${item.item_key}`}
                          className={`flex items-start gap-2 rounded-lg border border-gray-100 bg-white px-2.5 py-2 ${
                            isMobile ? "flex-col" : ""
                          }`}
                        >
                          <div className="min-w-0 flex-1">
                            {routeCase?.maps_route_url ? (
                              <RouteMapEmbed
                                mapsRouteUrl={routeCase.maps_route_url}
                                caseId={routeCase.case_id}
                                title={routeCase.title}
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
            ),
          };
        })}
      />
    </div>
  );
}
