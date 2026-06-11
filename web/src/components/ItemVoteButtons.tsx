import type { ItemVote } from "../api/types";

interface ItemVoteButtonsProps {
  vote: ItemVote | null;
  disabled?: boolean;
  horizontal?: boolean;
  className?: string;
  onVote: (vote: ItemVote | null) => void;
}

export function ItemVoteButtons({
  vote,
  disabled,
  horizontal = false,
  className = "",
  onVote,
}: ItemVoteButtonsProps) {
  return (
    <div
      className={`flex shrink-0 ${horizontal ? "flex-row items-center gap-0.5" : "flex-col gap-1 pt-0.5"} ${className}`}
    >
      <button
        type="button"
        disabled={disabled}
        aria-label="Нравится"
        aria-pressed={vote === 1}
        className={`rounded-md leading-none transition-opacity hover:bg-green-50 disabled:opacity-40 ${
          horizontal ? "px-1.5 py-0.5 text-base" : "px-2 py-1 text-lg"
        } ${
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
        className={`rounded-md leading-none transition-opacity hover:bg-red-50 disabled:opacity-40 ${
          horizontal ? "px-1.5 py-0.5 text-base" : "px-2 py-1 text-lg"
        } ${
          vote === -1 ? "bg-red-50 ring-1 ring-red-300" : "opacity-70 hover:opacity-100"
        }`}
        onClick={() => onVote(vote === -1 ? null : -1)}
      >
        👎
      </button>
    </div>
  );
}
