import { CompassOutlined, MenuOutlined } from "@ant-design/icons";
import { Button, Drawer, Grid, Layout, Menu } from "antd";
import { useState } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { NewTripPage } from "./pages/NewTripPage";
import { TripDetailPage } from "./pages/TripDetailPage";
import { TripListPage } from "./pages/TripListPage";

const { Header, Content } = Layout;
const { useBreakpoint } = Grid;

const NAV_ITEMS = [
  { key: "list", label: "Поездки", to: "/" },
  { key: "new", label: "Новая поездка", to: "/trips/new" },
] as const;

export default function App() {
  const location = useLocation();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [drawerOpen, setDrawerOpen] = useState(false);

  const selectedKey = location.pathname.startsWith("/trips/new")
    ? "new"
    : location.pathname.startsWith("/trips/")
      ? "trip"
      : "list";

  const menuItems = NAV_ITEMS.map(({ key, label, to }) => ({
    key,
    label: (
      <Link to={to} onClick={() => setDrawerOpen(false)}>
        {label}
      </Link>
    ),
  }));

  return (
    <Layout className="min-h-screen flex flex-1 flex-col bg-[#f5f5f5]">
      <Header className="app-header flex shrink-0 items-center gap-2 px-3 sm:gap-6 sm:px-6">
        {isMobile ? (
          <Button
            type="text"
            aria-label="Меню"
            icon={<MenuOutlined />}
            className="!text-white shrink-0"
            onClick={() => setDrawerOpen(true)}
          />
        ) : null}
        <Link
          to="/"
          className="flex min-w-0 flex-1 items-center gap-2 text-white text-base font-medium sm:flex-none sm:text-lg"
        >
          <CompassOutlined className="shrink-0" />
          <span className="truncate">{isMobile ? "Туризм" : "Туристический ассистент"}</span>
        </Link>
        {!isMobile ? (
          <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[selectedKey]}
            className="min-w-0 flex-1 border-0"
            items={menuItems}
          />
        ) : null}
        <Drawer
          title="Меню"
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          styles={{ body: { padding: 0 } }}
        >
          <Menu mode="inline" selectedKeys={[selectedKey]} items={menuItems} />
        </Drawer>
      </Header>
      <Content className="app-content mx-auto flex flex-1 w-full max-w-5xl flex-col px-3 py-4 sm:px-4 sm:py-6">
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
