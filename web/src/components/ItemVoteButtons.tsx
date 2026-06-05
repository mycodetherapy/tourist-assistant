import type { ItemVote } from "../api/types";

interface ItemVoteButtonsProps {
  vote: ItemVote | null;
  disabled?: boolean;
  onVote: (vote: ItemVote | null) => void;
}

export function ItemVoteButtons({ vote, disabled, onVote }: ItemVoteButtonsProps) {
  return (
    <div className="flex shrink-0 flex-col gap-1 pt-0.5">
      <button
        type="button"
        disabled={disabled}
        aria-label="Нравится"
        aria-pressed={vote === 1}
        className={`rounded-md px-2 py-1 text-lg leading-none transition-opacity hover:bg-green-50 disabled:opacity-40 ${
          vote === 1 ? "bg-green-50 ring-1 ring-green-300" : "opacity-70 hover:opacity-100"
        }`}
        onClick={() => onVote(vote === 1 ? null : 1)}
      >
        👍
      </button>
      <button
        type="button"
        disabled={disabled}
        aria-label="Не нравится"
        aria-pressed={vote === -1}
        className={`rounded-md px-2 py-1 text-lg leading-none transition-opacity hover:bg-red-50 disabled:opacity-40 ${
          vote === -1 ? "bg-red-50 ring-1 ring-red-300" : "opacity-70 hover:opacity-100"
        }`}
        onClick={() => onVote(vote === -1 ? null : -1)}
      >
        👎
      </button>
    </div>
  );
}
