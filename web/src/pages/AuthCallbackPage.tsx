import { Spin } from "antd";
import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { completeLogin } = useAuth();

  useEffect(() => {
    const claimedTripId = params.get("trip");
    void completeLogin()
      .then(() => {
        if (claimedTripId) {
          navigate(`/trips/${claimedTripId}`, { replace: true });
          return;
        }
        navigate("/settings", { replace: true, state: { onboarding: true } });
      })
      .catch(() => navigate("/login", { replace: true }));
  }, [params, navigate, completeLogin]);

  return (
    <div className="flex flex-1 items-center justify-center py-24">
      <Spin size="large" tip="Вход через Google…" />
    </div>
  );
}
