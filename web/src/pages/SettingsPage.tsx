import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Spin, Typography, notification } from "antd";
import { Link } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { deleteLlmKey, fetchSettings, updateSettings } from "../api/settings";
import type { UpdateSettingsPayload } from "../api/types";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<UpdateSettingsPayload>();

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  const saveMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      notification.success({ title: "Настройки сохранены" });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      form.setFieldValue("llm_api_key", "");
    },
    onError: (error) => {
      notification.error({ title: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLlmKey,
    onSuccess: () => {
      notification.success({ title: "Ключ удалён" });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (error) => {
      notification.error({ title: "Ошибка", description: getErrorMessage(error) });
    },
  });

  if (settingsQuery.isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spin size="large" />
      </div>
    );
  }

  const settings = settingsQuery.data;

  return (
    <div className="mx-auto w-full max-w-lg">
      <h1 className="mb-4 text-xl font-semibold sm:text-2xl">Настройки</h1>
      <Alert
        className="mb-4"
        type="info"
        showIcon
        message="OpenRouter BYOK"
        description={
          <>
            Укажите свой API-ключ с{" "}
            <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer">
              openrouter.ai/keys
            </a>
            . Сборка программы оплачивается с вашего баланса OpenRouter.
          </>
        }
      />
      <Card>
        {settings?.llm_key_configured ? (
          <Typography.Paragraph type="secondary">
            Текущий ключ: <code>{settings.llm_key_preview}</code>
          </Typography.Paragraph>
        ) : (
          <Typography.Paragraph type="warning">
            Ключ не задан — без него нельзя запустить сборку программы.
          </Typography.Paragraph>
        )}
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            llm_base_url: settings?.llm_base_url,
            llm_model: settings?.llm_model,
          }}
          onFinish={(values) => saveMutation.mutate(values)}
        >
          <Form.Item name="llm_api_key" label="OpenRouter API key">
            <Input.Password
              placeholder="sk-or-..."
              autoComplete="off"
            />
          </Form.Item>
          <Form.Item name="llm_base_url" label="Base URL">
            <Input placeholder="https://openrouter.ai/api/v1" />
          </Form.Item>
          <Form.Item name="llm_model" label="Модель">
            <Input placeholder="openai/gpt-4.1-mini" />
          </Form.Item>
          <div className="flex flex-wrap gap-2">
            <Button type="primary" htmlType="submit" loading={saveMutation.isPending}>
              Сохранить
            </Button>
            {settings?.llm_key_configured ? (
              <Button danger loading={deleteMutation.isPending} onClick={() => deleteMutation.mutate()}>
                Удалить ключ
              </Button>
            ) : null}
            <Link to="/">
              <Button type="link">К поездкам</Button>
            </Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
