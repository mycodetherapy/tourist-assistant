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
        message="BYOK: свой ключ LLM"
        description={
          <>
            <p className="m-0 mb-2">
              Укажите API-ключ вашего провайдера (ProxyAPI, OpenRouter и др.), Base URL и модель.
              Сборка программы оплачивается с вашего баланса у выбранного провайдера.
            </p>
            <p className="m-0">
              <strong>Из РФ</strong> удобнее{" "}
              <a href="https://proxyapi.ru" target="_blank" rel="noopener noreferrer">
                ProxyAPI
              </a>
              : работает без VPN. Зарегистрируйтесь, получите ключ в личном кабинете и вставьте его
              ниже — Base URL (<code>https://openai.api.proxyapi.ru/v1</code>) и модель (
              <code>gemini/gemini-2.5-flash</code>) уже подставлены по умолчанию.
            </p>
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
          <Form.Item name="llm_api_key" label="API key">
            <Input.Password
              placeholder="sk-..."
              autoComplete="off"
            />
          </Form.Item>
          <Form.Item name="llm_base_url" label="Base URL">
            <Input placeholder="https://openai.api.proxyapi.ru/v1" />
          </Form.Item>
          <Form.Item name="llm_model" label="Модель">
            <Input placeholder="gemini/gemini-2.5-flash" />
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
            <Link to="/trips">
              <Button type="link">К поездкам</Button>
            </Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
