import { Card, Descriptions, Tag } from "antd";
import type { TripDetail } from "../api/types";

const STATUS_COLORS: Record<string, string> = {
  building: "processing",
  review: "warning",
  approved: "success",
  draft: "default",
  failed: "error",
};

interface TripMetaCardProps {
  trip: TripDetail;
}

export function TripMetaCard({ trip }: TripMetaCardProps) {
  return (
    <Card title={`Поездка #${trip.id}`}>
      <Descriptions column={1} size="small">
        <Descriptions.Item label="Маршрут">
          {trip.origin_city} → {trip.city}
        </Descriptions.Item>
        <Descriptions.Item label="Даты">{trip.dates}</Descriptions.Item>
        <Descriptions.Item label="Статус">
          <Tag color={STATUS_COLORS[trip.status] ?? "default"}>{trip.status}</Tag>
        </Descriptions.Item>
        {trip.user_query && (
          <Descriptions.Item label="Запрос">{trip.user_query}</Descriptions.Item>
        )}
      </Descriptions>
    </Card>
  );
}
