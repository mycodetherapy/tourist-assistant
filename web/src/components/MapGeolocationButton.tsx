import { AimOutlined } from "@ant-design/icons";

interface MapGeolocationButtonProps {
  locating: boolean;
  onClick: () => void;
  topClassName?: string;
}

/** Кнопка «моё местоположение» поверх карты Яндекс.Карт. */
export function MapGeolocationButton({
  locating,
  onClick,
  topClassName = "top-[72px]",
}: MapGeolocationButtonProps) {
  return (
    <button
      type="button"
      aria-label="Показать моё местоположение"
      disabled={locating}
      onClick={onClick}
      className={`absolute right-2.5 z-20 flex h-[38px] w-[38px] items-center justify-center rounded-lg border border-black/10 bg-white text-base text-gray-700 shadow-md transition hover:bg-gray-50 disabled:cursor-wait disabled:opacity-70 ${topClassName}`}
    >
      <AimOutlined spin={locating} />
    </button>
  );
}
