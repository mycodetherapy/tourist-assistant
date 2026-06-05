import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Tabs, notification } from "antd";
import ReactMarkdown from "react-markdown";
import { getErrorMessage } from "../api/client";
import { submitItemFeedback } from "../api/trips";
import type { ItemVote, ProgramResponse, VotableSectionKey } from "../api/types";
import { ItemVoteButtons } from "./ItemVoteButtons";

interface ProgramTabsProps {
  tripId: number;
  data: ProgramResponse;
  votingDisabled?: boolean;
}

const TABS: { key: "tickets" | VotableSectionKey; label: string; votable: boolean }[] = [
  { key: "tickets", label: "Билеты", votable: false },
  { key: "events", label: "Мероприятия", votable: true },
  { key: "dining", label: "Питание", votable: true },
  { key: "lifehacks", label: "Лайфхаки", votable: true },
];

function MarkdownBlock({ text, className = "mb-4" }: { text: string; className?: string }) {
  if (!text.trim()) {
    return null;
  }
  return (
    <div className={`prose max-w-none whitespace-pre-wrap ${className}`}>
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
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
    <Tabs
      items={TABS.map(({ key, label, votable }) => {
        if (!votable) {
          return {
            key,
            label,
            children: <MarkdownBlock text={data.program.tickets} className="" />,
          };
        }

        const sectionKey = key as VotableSectionKey;
        const section = data.sections[sectionKey];
        return {
          key,
          label,
          children: (
            <div>
              <MarkdownBlock text={section.intro} />
              {section.items.length === 0 ? (
                <p className="text-gray-500">Нет пунктов в этой секции.</p>
              ) : (
                <ul className="space-y-3">
                  {section.items.map((item) => (
                    <li
                      key={`${sectionKey}-${item.item_key}`}
                      className="flex items-start gap-3 rounded-lg border border-gray-100 bg-white px-3 py-2"
                    >
                      <div className="min-w-0 flex-1">
                        <MarkdownBlock text={item.text} className="" />
                      </div>
                      <ItemVoteButtons
                        vote={item.vote}
                        disabled={votingDisabled || voteMutation.isPending}
                        onVote={(vote) =>
                          handleVote(sectionKey, item.index, item.item_key, vote)
                        }
                      />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ),
        };
      })}
    />
  );
}
