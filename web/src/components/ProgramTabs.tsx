import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Tabs, notification } from "antd";
import ReactMarkdown from "react-markdown";
import { getErrorMessage } from "../api/client";
import { submitItemFeedback } from "../api/trips";
import { parseRouteProgram } from "../api/routeTypes";
import type { ItemVote, ProgramResponse, VotableSectionKey } from "../api/types";
import { ItemVoteButtons } from "./ItemVoteButtons";
import { RouteCaseDetails } from "./RouteCaseDetails";
import { RouteMapEmbed } from "./RouteMapEmbed";

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

function MarkdownBlock({ text, className = "mb-4" }: { text: string; className?: string }) {
  if (!text.trim()) {
    return null;
  }
  return (
    <div className={`prose max-w-none whitespace-pre-wrap ${className}`}>
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 underline">
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
  const tabs = buildTabs(data);
  const legacy = isLegacyProgram(data);
  const routeCases = parseRouteProgram(data.program.routes);

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
    onSuccess: (updated) => {
      queryClient.setQueryData(["trips", tripId, "program"], updated);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["trips", tripId, "program"] });
    },
    onError: (error) => {
      notification.error({
        message: "Оценка не сохранена",
        description: getErrorMessage(error),
      });
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
              ? "Использованы демо-точки: нужен ключ API Геокодера в YANDEX_MAPS_API_KEY. python3 scripts/test_yandex_maps.py"
              : "Оцените варианты A / B / C. Карта встроена в каждый вариант; ссылка на Яндекс.Карты — в описании."
          }
        />
      )}
      <Tabs
        items={tabs.map(({ key, label, votable }) => {
          if (!votable) {
            return {
              key,
              label,
              children: <MarkdownBlock text={data.program.tickets} className="" />,
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
                        sectionKey === "routes" ? routeCases[item.index] : undefined;
                      const useRouteCard =
                        sectionKey === "routes" &&
                        routeCase &&
                        Boolean(routeCase.maps_route_url || routeCase.stops.length);
                      return (
                      <li
                        key={`${sectionKey}-${item.item_key}`}
                        className="flex items-start gap-2 rounded-lg border border-gray-100 bg-white px-2.5 py-2"
                      >
                        <div className="min-w-0 flex-1">
                          {routeCase?.maps_route_url ? (
                            <RouteMapEmbed
                              mapsRouteUrl={routeCase.maps_route_url}
                              caseId={routeCase.case_id}
                              title={routeCase.title}
                            />
                          ) : null}
                          {useRouteCard ? (
                            <RouteCaseDetails routeCase={routeCase} />
                          ) : (
                            <MarkdownBlock text={item.text} className="mb-0" />
                          )}
                        </div>
                        <ItemVoteButtons
                          vote={item.vote}
                          disabled={votingDisabled || voteMutation.isPending}
                          onVote={(vote) =>
                            handleVote(sectionKey, item.index, item.item_key, vote)
                          }
                        />
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
