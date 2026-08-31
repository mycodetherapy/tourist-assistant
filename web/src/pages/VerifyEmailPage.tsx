import { Alert, Button, Spin, Typography, notification } from "antd";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { verifyEmail } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const { setTokenFromOAuth } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!token) {
        setError("В ссылке нет токена подтверждения");
        return;
      }
      try {
        const data = await verifyEmail(token);
        if (cancelled) return;
        await setTokenFromOAuth(data.access_token);
        setDone(true);
        notification.success({ title: "Email подтверждён" });
        window.setTimeout(() => navigate("/settings", { replace: true }), 1200);
      } catch (err) {
        if (!cancelled) {
          setError(getErrorMessage(err));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, navigate, setTokenFromOAuth]);

  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md flex-col justify-center px-4 py-12">
      <Typography.Title level={3}>Подтверждение email</Typography.Title>
      {!error && !done ? (
        <div className="flex justify-center py-8">
          <Spin size="large" description="Проверяем ссылку…" />
        </div>
      ) : null}
      {done ? (
        <Alert type="success" showIcon message="Готово. Переходим в настройки…" />
      ) : null}
      {error ? (
        <>
          <Alert type="error" showIcon message={error} className="mb-4" />
          <Link to="/settings">
            <Button type="primary">В настройки</Button>
          </Link>
        </>
      ) : null}
    </div>
  );
}
