import { Alert, Descriptions } from "antd";
import type { TripPreferences } from "../api/types";

const PARTY_LABELS: Record<TripPreferences["travel_party"], string> = {
  solo: "1 взрослый",
  couple: "2 взрослых",
  family: "2 взрослых + 1 ребёнок",
  parent_child: "1 взрослый + 1 ребёнок",
  family_two: "2 взрослых + 2 ребёнка",
  friends: "3 взрослых",
};

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
        description="Билеты туда-обратно и три альтернативных маршрута на всю поездку (варианты A, B, C) с местами досуга из Wikidata. У каждого варианта — ссылка «Открыть маршрут в Яндекс.Картах» и лайфхаки."
      />
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Маршрут">
          {originCity} → {city}
        </Descriptions.Item>
        <Descriptions.Item label="Даты">{dates}</Descriptions.Item>
        <Descriptions.Item label="Состав группы">
          {PARTY_LABELS[preferences.travel_party]}
        </Descriptions.Item>
        <Descriptions.Item label="Темп и передвижение">
          Насыщенный; метро + пешком
        </Descriptions.Item>
      </Descriptions>
      <p className="text-sm text-neutral-500">
        POI из Wikidata; проверка пула:{" "}
        <code className="text-xs">python3 scripts/test_yandex_maps.py {city}</code>
      </p>
    </div>
  );
}
