import { GoogleOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Typography, notification } from "antd";
import { useEffect, useState, type MouseEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { googleLoginUrl } from "../api/auth";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { LegalConsentFields } from "../components/LegalConsentFields";
import { METRIKA_GOALS, reachGoal } from "../utils/analytics";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("return");
  const [form] = Form.useForm<{
    email: string;
    password: string;
    confirm: string;
    accept_terms: boolean;
    accept_privacy: boolean;
  }>();
  const [consentOk, setConsentOk] = useState(false);

  useEffect(() => {
    reachGoal(METRIKA_GOALS.REGISTER_PAGE_VIEW);
  }, []);

  const syncConsent = () => {
    const v = form.getFieldsValue(["accept_terms", "accept_privacy"]);
    setConsentOk(Boolean(v.accept_terms && v.accept_privacy));
  };

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      const claimedTripId = await register(values.email, values.password);
      reachGoal(METRIKA_GOALS.REGISTER_SUCCESS);
      if (claimedTripId) {
        navigate(`/trips/${claimedTripId}`, { replace: true });
        return;
      }
      if (returnTo?.startsWith("/")) {
        navigate(returnTo, { replace: true });
        return;
      }
      navigate("/settings", { replace: true, state: { onboarding: true } });
    } catch (error) {
      notification.error({ title: "Ошибка регистрации", description: getErrorMessage(error) });
    }
  };

  const onGoogleClick = async (e: MouseEvent) => {
    try {
      await form.validateFields(["accept_terms", "accept_privacy"]);
    } catch {
      e.preventDefault();
      notification.warning({
        title: "Нужно согласие",
        description: "Примите соглашение и дайте согласие на обработку персональных данных.",
      });
    }
  };

  return (
    <div className="mx-auto w-full max-w-md">
      <Card title="Регистрация">
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          onValuesChange={syncConsent}
          initialValues={{ accept_terms: false, accept_privacy: false }}
        >
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
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="Повтор пароля"
            dependencies={["password"]}
            rules={[
              { required: true, message: "Повторите пароль" },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("password") === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error("Пароли не совпадают"));
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <LegalConsentFields />
          <Button type="primary" htmlType="submit" block>
            Создать аккаунт
          </Button>
        </Form>
        <div className="mt-4 flex flex-col gap-2">
          <Button
            icon={<GoogleOutlined />}
            href={consentOk ? googleLoginUrl() : undefined}
            block
            disabled={!consentOk}
            onClick={(e) => void onGoogleClick(e)}
          >
            Регистрация через Google
          </Button>
          {!consentOk ? (
            <Typography.Text type="secondary" className="text-xs">
              Отметьте согласия выше, чтобы зарегистрироваться через Google.
            </Typography.Text>
          ) : null}
          <Typography.Text type="secondary">
            Уже есть аккаунт? <Link to="/login">Войти</Link>
          </Typography.Text>
        </div>
      </Card>
    </div>
  );
}
