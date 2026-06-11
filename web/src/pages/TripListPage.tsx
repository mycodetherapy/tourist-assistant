import { PlusOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Empty, notification } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { deleteTrip } from "../api/trips";
import { TripTable } from "../components/TripTable";
import { useTrips } from "../hooks/useTrips";

export function TripListPage() {
  const queryClient = useQueryClient();
  const { data: trips = [], isLoading } = useTrips();
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const deleteMutation = useMutation({
    mutationFn: async (tripId: number) => {
      setDeletingId(tripId);
      await deleteTrip(tripId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      notification.success({ message: "Поездка удалена" });
    },
    onError: (error) => {
      notification.error({ message: "Ошибка", description: getErrorMessage(error) });
    },
    onSettled: () => {
      setDeletingId(null);
    },
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 sm:mb-6">
        <h1 className="m-0 text-xl font-semibold sm:text-2xl">Поездки</h1>
        <Link to="/trips/new" className="w-full sm:w-auto">
          <Button type="primary" icon={<PlusOutlined />} block className="sm:!w-auto">
            Новая поездка
          </Button>
        </Link>
      </div>
      {!isLoading && trips.length === 0 ? (
        <Empty description="Поездок пока нет">
          <Link to="/trips/new">
            <Button type="primary">Создать первую поездку</Button>
          </Link>
        </Empty>
      ) : (
        <TripTable
          trips={trips}
          loading={isLoading}
          deletingId={deletingId}
          onDelete={(tripId) => deleteMutation.mutate(tripId)}
        />
      )}
    </div>
  );
}
