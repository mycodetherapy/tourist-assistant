import { GoogleOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Typography, notification } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { googleLoginUrl } from "../api/auth";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form] = Form.useForm<{ email: string; password: string }>();

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      await login(values.email, values.password);
      navigate("/", { replace: true });
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
            rules={[{ required: true, message: "Введите пароль" }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Войти
          </Button>
        </Form>
        <div className="mt-4 flex flex-col gap-2">
          <Button icon={<GoogleOutlined />} href={googleLoginUrl()} block>
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
