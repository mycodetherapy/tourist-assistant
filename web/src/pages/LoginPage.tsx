import { GoogleOutlined } from "@ant-design/icons";
import { Button, Card, Checkbox, Form, Input, Typography, notification } from "antd";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { googleLoginUrl } from "../api/auth";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const OAUTH_ERRORS: Record<string, string> = {
  oauth_state: "Сессия Google истекла или cookies заблокированы. Попробуйте снова.",
  oauth_denied: "Вход через Google отменён.",
  oauth_failed: "Не удалось войти через Google. Проверьте настройки на сервере или попробуйте позже.",
};

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [form] = Form.useForm<{ email: string; password: string }>();
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const googleOk = acceptTerms && acceptPrivacy;

  useEffect(() => {
    const code = params.get("error");
    if (!code) return;
    notification.error({
      title: "Google",
      description: OAUTH_ERRORS[code] ?? "Ошибка авторизации Google.",
    });
    params.delete("error");
    setParams(params, { replace: true });
  }, [params, setParams]);

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      const claimedTripId = await login(values.email, values.password);
      if (claimedTripId) {
        navigate(`/trips/${claimedTripId}`, { replace: true });
        return;
      }
      navigate("/trips", { replace: true });
    } catch (error) {
      notification.error({ title: "Ошибка входа", description: getErrorMessage(error) });
    }
  };

  return (
    <div className="mx-auto w-full max-w-md">
      <Card title="Вход">
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="email"
            label="Email"
            rules={[{ required: true, type: "email", message: "Введите email" }]}
          >
            <Input autoComplete="email" />
          </Form.Item>
          <Form.Item
            name="password"
            label="Пароль"
            rules={[
              { required: true, message: "Введите пароль" },
              { min: 8, message: "Минимум 8 символов" },
            ]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Войти
          </Button>
        </Form>
        <div className="mt-4 flex flex-col gap-2">
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
            <Checkbox
              checked={acceptTerms}
              onChange={(e) => setAcceptTerms(e.target.checked)}
              className="!items-start"
            >
              Принимаю{" "}
              <Link to="/terms" target="_blank" className="text-sky-700 underline">
                Пользовательское соглашение
              </Link>
            </Checkbox>
            <div className="mt-2">
              <Checkbox
                checked={acceptPrivacy}
                onChange={(e) => setAcceptPrivacy(e.target.checked)}
                className="!items-start"
              >
                Согласие на обработку ПДн по{" "}
                <Link to="/privacy" target="_blank" className="text-sky-700 underline">
                  Политике конфиденциальности
                </Link>
              </Checkbox>
            </div>
            <Typography.Text type="secondary" className="mt-2 block text-xs">
              Нужно для входа через Google (в т.ч. при первом создании аккаунта).
            </Typography.Text>
          </div>
          <Button
            icon={<GoogleOutlined />}
            href={googleOk ? googleLoginUrl() : undefined}
            block
            disabled={!googleOk}
          >
            Войти через Google
          </Button>
          <Typography.Text type="secondary">
            Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
          </Typography.Text>
        </div>
      </Card>
    </div>
  );
}
