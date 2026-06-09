import { Alert, Descriptions } from "antd";
import type { TripPreferences } from "../api/types";

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
        <Descriptions.Item label="Темп">{preferences.pace}</Descriptions.Item>
        <Descriptions.Item label="Рестораны от">
          {preferences.min_restaurant_rating} ★
        </Descriptions.Item>
      </Descriptions>
      <p className="text-sm text-neutral-500">
        POI берутся из OpenStreetMap (Overpass) и Wikidata; проверка пула:{" "}
        <code className="text-xs">python3 scripts/test_yandex_maps.py Самара</code>
      </p>
    </div>
  );
}
