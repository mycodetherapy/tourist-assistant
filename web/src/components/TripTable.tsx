import { DeleteOutlined } from "@ant-design/icons";
import { Button, Grid, Popconfirm, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link, useNavigate } from "react-router-dom";
import type { TripSummary } from "../api/types";

const { useBreakpoint } = Grid;

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

function statusColumn(mobile = false): ColumnsType<TripSummary>[number] {
  return {
    title: "Статус",
    dataIndex: "status",
    ...(mobile ? { align: "right" as const, className: "trip-mobile-status-col" } : {}),
    render: (status: string) => (
      <Tag color={STATUS_COLORS[status] ?? "default"}>{status}</Tag>
    ),
  };
}

export function TripTable({ trips, loading, deletingId, onDelete }: TripTableProps) {
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const isMobile = screens.md === false;

  const desktopColumns: ColumnsType<TripSummary> = [
    { title: "ID", dataIndex: "id", width: 70 },
    { title: "Город", dataIndex: "city" },
    { title: "Даты", dataIndex: "dates" },
    {
      title: "Маршрут",
      render: (_, row) => `${row.origin_city} → ${row.city}`,
    },
    statusColumn(),
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
  ];

  const mobileColumns: ColumnsType<TripSummary> = [
    {
      title: "Город",
      dataIndex: "city",
      ellipsis: true,
      className: "trip-mobile-split-col",
    },
    {
      title: "Даты",
      dataIndex: "dates",
      ellipsis: true,
      className: "trip-mobile-split-col",
    },
    statusColumn(true),
  ];

  return (
    <Table
      rowKey="id"
      loading={loading}
      dataSource={trips}
      pagination={{ pageSize: 10 }}
      className={isMobile ? "trip-table-mobile" : undefined}
      tableLayout={isMobile ? "fixed" : "auto"}
      columns={isMobile ? mobileColumns : desktopColumns}
      onRow={
        isMobile
          ? (record) => ({
              onClick: () => navigate(`/trips/${record.id}`),
              className: "cursor-pointer active:bg-gray-50",
            })
          : undefined
      }
    />
  );
}
