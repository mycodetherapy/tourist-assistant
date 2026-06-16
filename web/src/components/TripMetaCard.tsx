import { Card, Descriptions } from "antd";
import type { TripDetail } from "../api/types";

interface TripMetaCardProps {
  trip: TripDetail;
}

export function TripMetaCard({ trip }: TripMetaCardProps) {
  return (
    <Card title={`Поездка #${trip.id}`}>
      <Descriptions column={1} size="small">
        <Descriptions.Item label="Город">{trip.city}</Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
