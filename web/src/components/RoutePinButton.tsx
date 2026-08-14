interface RoutePinButtonProps {
  pinned: boolean;
  disabled?: boolean;
  horizontal?: boolean;
  className?: string;
  onToggle: (pinned: boolean) => void;
}

export function RoutePinButton({
  pinned,
  disabled,
  horizontal = false,
  className = "",
  onToggle,
}: RoutePinButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      title={
        pinned
          ? "Сохранён при пересборе — нажмите, чтобы снять"
          : "Сохранить маршрут: останется при пересборе A/B/C"
      }
      aria-label={pinned ? "Снять сохранение маршрута" : "Сохранить маршрут при пересборе"}
      aria-pressed={pinned}
      className={`rounded-md leading-none transition-opacity hover:bg-amber-50 disabled:opacity-40 ${
        horizontal ? "px-1.5 py-0.5 text-base" : "px-2 py-1 text-lg"
      } ${
        pinned ? "bg-amber-50 ring-1 ring-amber-300" : "opacity-70 hover:opacity-100"
      } ${className}`}
      onClick={() => onToggle(!pinned)}
    >
      📌
    </button>
  );
}
