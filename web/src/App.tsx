import { CompassOutlined, LogoutOutlined, MenuOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Drawer, Grid, Layout, Menu, Popconfirm } from "antd";
import { useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { LoginPage } from "./pages/LoginPage";
import { NewTripPage } from "./pages/NewTripPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TripDetailPage } from "./pages/TripDetailPage";
import { TripListPage } from "./pages/TripListPage";

const { Header, Content } = Layout;
const { useBreakpoint } = Grid;

const NAV_ITEMS = [
  { key: "list", label: "Поездки", to: "/" },
  { key: "new", label: "Новая поездка", to: "/trips/new" },
  { key: "settings", label: "Настройки", to: "/settings" },
] as const;

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isAuthPage =
    location.pathname === "/login" ||
    location.pathname === "/register" ||
    location.pathname === "/auth/callback";

  const selectedKey = location.pathname.startsWith("/settings")
    ? "settings"
    : location.pathname.startsWith("/trips/new")
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
      {!isAuthPage ? (
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
          {user ? (
            <div className="flex shrink-0 items-center gap-1 sm:gap-2">
              {!isMobile ? (
                <span className="hidden max-w-[140px] truncate text-white/80 text-sm sm:inline md:max-w-[200px]">
                  {user.email}
                </span>
              ) : null}
              <Button
                type="text"
                aria-label="Настройки"
                icon={<SettingOutlined />}
                className="!text-white"
                onClick={() => navigate("/settings")}
              />
              <Popconfirm
                title="Вы действительно хотите выйти?"
                okText="Выйти"
                cancelText="Отмена"
                onConfirm={() => {
                  logout();
                  navigate("/login", { replace: true });
                }}
              >
                <Button
                  type="text"
                  aria-label="Выйти"
                  icon={<LogoutOutlined />}
                  className="!text-white"
                />
              </Popconfirm>
            </div>
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
      ) : null}
      <Content className="app-content mx-auto flex flex-1 w-full max-w-5xl flex-col px-3 py-4 sm:px-4 sm:py-6">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <TripListPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/trips/new"
            element={
              <ProtectedRoute>
                <NewTripPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/trips/:id"
            element={
              <ProtectedRoute>
                <TripDetailPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}
