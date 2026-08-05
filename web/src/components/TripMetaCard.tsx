import { Card, Descriptions } from "antd";
import type { TripDetail } from "../api/types";

interface TripMetaCardProps {
  trip: TripDetail;
  guestMode?: boolean;
}

function tripTitle(trip: TripDetail, guestMode: boolean): string {
  if (guestMode) {
    return trip.city.trim() ? `Прогулка: ${trip.city.trim()}` : "Гостевая прогулка";
  }
  return `Прогулка #${trip.id}`;
}

export function TripMetaCard({ trip, guestMode = false }: TripMetaCardProps) {
  return (
    <Card title={tripTitle(trip, guestMode)}>
      <Descriptions column={1} size="small">
        <Descriptions.Item label="Город">{trip.city}</Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
