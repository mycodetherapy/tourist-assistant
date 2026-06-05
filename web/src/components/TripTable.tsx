import { DeleteOutlined } from "@ant-design/icons";
import { Button, Popconfirm, Space, Table, Tag } from "antd";
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
  deletingId?: number | null;
  onDelete: (tripId: number) => void;
}

export function TripTable({ trips, loading, deletingId, onDelete }: TripTableProps) {
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
          width: 200,
          render: (_, row) => (
            <Space>
              <Link to={`/trips/${row.id}`}>
                <Button type="link">Открыть</Button>
              </Link>
              <Popconfirm
                title={`Удалить поездку #${row.id}?`}
                description={`${row.city}, ${row.dates}`}
                okText="Удалить"
                cancelText="Отмена"
                okButtonProps={{ danger: true }}
                onConfirm={() => onDelete(row.id)}
              >
                <Button
                  type="link"
                  danger
                  icon={<DeleteOutlined />}
                  loading={deletingId === row.id}
                >
                  Удалить
                </Button>
              </Popconfirm>
            </Space>
          ),
        },
      ]}
    />
  );
}
