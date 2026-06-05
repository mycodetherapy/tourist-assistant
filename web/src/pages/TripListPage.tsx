import { PlusOutlined } from "@ant-design/icons";
import { Button, Empty } from "antd";
import { Link } from "react-router-dom";
import { TripTable } from "../components/TripTable";
import { useTrips } from "../hooks/useTrips";

export function TripListPage() {
  const { data: trips = [], isLoading } = useTrips();

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold m-0">Поездки</h1>
        <Link to="/trips/new">
          <Button type="primary" icon={<PlusOutlined />}>
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
        <TripTable trips={trips} loading={isLoading} />
      )}
    </div>
  );
}
