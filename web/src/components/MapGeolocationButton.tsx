import { AimOutlined } from "@ant-design/icons";

interface MapGeolocationButtonProps {
  locating: boolean;
  active?: boolean;
  onClick: () => void;
  topClassName?: string;
  /** Переопределение aria-label (например «Следовать по маршруту»). */
  ariaLabel?: string;
}

/** Кнопка «моё местоположение» / follow поверх карты. */
export function MapGeolocationButton({
  locating,
  active = false,
  onClick,
  topClassName = "top-[72px]",
  ariaLabel,
}: MapGeolocationButtonProps) {
  const label =
    ariaLabel ??
    (active ? "Скрыть моё местоположение" : "Показать моё местоположение");
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-pressed={active}
      disabled={locating}
      onClick={onClick}
      className={`absolute right-2.5 z-20 flex h-[38px] w-[38px] items-center justify-center rounded-lg border shadow-md transition hover:bg-gray-50 disabled:cursor-wait disabled:opacity-70 ${topClassName} ${
        active
          ? "border-blue-500 bg-blue-50 text-blue-600"
          : "border-black/10 bg-white text-base text-gray-700"
      }`}
    >
      <AimOutlined spin={locating} />
    </button>
  );
}
