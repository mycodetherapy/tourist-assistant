import { CompassOutlined } from "@ant-design/icons";
import { Layout, Menu } from "antd";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { NewTripPage } from "./pages/NewTripPage";
import { TripDetailPage } from "./pages/TripDetailPage";
import { TripListPage } from "./pages/TripListPage";

const { Header, Content } = Layout;

export default function App() {
  const location = useLocation();
  const selectedKey = location.pathname.startsWith("/trips/new")
    ? "new"
    : location.pathname.startsWith("/trips/")
      ? "trip"
      : "list";

  return (
    <Layout className="min-h-screen">
      <Header className="flex items-center gap-6 px-6">
        <Link to="/" className="flex items-center gap-2 text-white text-lg font-medium">
          <CompassOutlined />
          Туристический ассистент
        </Link>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          className="flex-1 min-w-0 border-0"
          items={[
            { key: "list", label: <Link to="/">Поездки</Link> },
            { key: "new", label: <Link to="/trips/new">Новая поездка</Link> },
          ]}
        />
      </Header>
      <Content className="mx-auto w-full max-w-5xl px-4 py-6">
        <Routes>
          <Route path="/" element={<TripListPage />} />
          <Route path="/trips/new" element={<NewTripPage />} />
          <Route path="/trips/:id" element={<TripDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}
