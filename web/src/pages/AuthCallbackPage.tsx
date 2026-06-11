import { Spin } from "antd";
import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { setTokenFromOAuth } = useAuth();

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      navigate("/login", { replace: true });
      return;
    }
    void setTokenFromOAuth(token)
      .then(() => navigate("/settings", { replace: true, state: { onboarding: true } }))
      .catch(() => navigate("/login", { replace: true }));
  }, [params, navigate, setTokenFromOAuth]);

  return (
    <div className="flex flex-1 items-center justify-center py-24">
      <Spin size="large" tip="Вход через Google…" />
    </div>
  );
}
