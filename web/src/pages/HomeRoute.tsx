import { Spin } from "antd";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { LandingPage } from "./LandingPage";

export function HomeRoute() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spin size="large" />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/trips" replace />;
  }

  return <LandingPage />;
}
