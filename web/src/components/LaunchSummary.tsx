import { Alert, Descriptions, Tag } from "antd";
import type { TripPreferences } from "../api/types";
import { LEISURE_LABELS } from "../utils/leisure";
import { normalizeLeisureCategories } from "../utils/preferences";

interface LaunchSummaryProps {
  city: string;
  dates: string;
  originCity: string;
  preferences: TripPreferences;
}

export function LaunchSummary({
  city,
  dates,
  originCity,
  preferences,
}: LaunchSummaryProps) {
  const leisure = normalizeLeisureCategories(preferences.leisure_categories);

  return (
    <div className="max-w-xl space-y-4">
      <Alert
        type="info"
        showIcon
        message="Что соберёт агент"
        description="Билеты туда-обратно и три альтернативных маршрута на всю поездку (варианты A, B, C) с местами досуга и ресторанами из Яндекс.Карт. У каждого варианта будет ссылка «Открыть маршрут в Яндекс.Картах»."
      />
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Маршрут">
          {originCity} → {city}
        </Descriptions.Item>
        <Descriptions.Item label="Даты">{dates}</Descriptions.Item>
        <Descriptions.Item label="Категории досуга">
          {leisure.map((tag) => (
            <Tag key={tag}>{LEISURE_LABELS[tag]}</Tag>
          ))}
        </Descriptions.Item>
        <Descriptions.Item label="Темп">{preferences.pace}</Descriptions.Item>
        <Descriptions.Item label="Рестораны от">
          {preferences.min_restaurant_rating} ★
        </Descriptions.Item>
      </Descriptions>
      <p className="text-sm text-neutral-500">
        Для реальных мест нужны ключи <code className="text-xs">YANDEX_MAPS_API_KEY</code> (Geocoder) и{" "}
        <code className="text-xs">YANDEX_SEARCH_API_KEY</code> (поиск организаций) в{" "}
        <code className="text-xs">.env</code>. Проверка:{" "}
        <code className="text-xs">python3 scripts/test_yandex_maps.py Москва</code>
      </p>
    </div>
  );
}
