import { Button, Table, Tag } from "antd";
import { Link } from "react-router-dom";
import type { TripSummary } from "../api/types";

const STATUS_COLORS: Record<string, string> = {
  building: "processing",
  review: "warning",
  approved: "success",
  draft: "default",
  failed: "error",
};

interface TripTableProps {
  trips: TripSummary[];
  loading?: boolean;
}

export function TripTable({ trips, loading }: TripTableProps) {
  return (
    <Table
      rowKey="id"
      loading={loading}
      dataSource={trips}
      pagination={{ pageSize: 10 }}
      columns={[
        { title: "ID", dataIndex: "id", width: 70 },
        { title: "Город", dataIndex: "city" },
        { title: "Даты", dataIndex: "dates" },
        {
          title: "Маршрут",
          render: (_, row) => `${row.origin_city} → ${row.city}`,
        },
        {
          title: "Статус",
          dataIndex: "status",
          render: (status: string) => (
            <Tag color={STATUS_COLORS[status] ?? "default"}>{status}</Tag>
          ),
        },
        {
          title: "",
          width: 120,
          render: (_, row) => (
            <Link to={`/trips/${row.id}`}>
              <Button type="link">Открыть</Button>
            </Link>
          ),
        },
      ]}
    />
  );
}
