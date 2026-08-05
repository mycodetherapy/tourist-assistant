import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Radio, Spin, Typography, notification } from "antd";
import { Link } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { deleteLlmKey, fetchSettings, updateSettings } from "../api/settings";
import type { LlmMode, UpdateSettingsPayload } from "../api/types";

type SettingsFormValues = UpdateSettingsPayload & { llm_mode: LlmMode };

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<SettingsFormValues>();
  const watchedMode = Form.useWatch("llm_mode", form);

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

  const settings = settingsQuery.data;
  const llmMode = watchedMode ?? settings?.llm_mode ?? "none";

  if (settingsQuery.isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-lg">
      <h1 className="mb-4 text-xl font-semibold sm:text-2xl">Настройки</h1>
      <Alert
        className="mb-4"
        type="info"
        showIcon
        message="Режим сборки маршрутов"
        description={
          <>
            <p className="m-0 mb-2">
              <strong>Бесплатно</strong> — маршруты строятся алгоритмом по открытым данным (до 30 сборок
              в сутки). Справки о городе и местах — из Wikipedia.
            </p>
            <p className="m-0">
              <strong>Свой API-ключ (BYOK)</strong> — полный AI: персонализация маршрутов и справки через
              LLM. Оплата — у вашего провайдера (ProxyAPI, OpenRouter). Ориентир стоимости одной AI-сборки:{" "}
              ~{settings?.estimated_ai_run_cost_rub ?? 4} ₽.
            </p>
          </>
        }
      />
      <Card>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            llm_mode: settings?.llm_mode ?? "none",
            llm_base_url: settings?.llm_base_url,
            llm_model: settings?.llm_model,
          }}
          onFinish={(values) => saveMutation.mutate(values)}
        >
          <Form.Item name="llm_mode" label="Режим AI">
            <Radio.Group>
              <Radio value="none">Бесплатно (алгоритм)</Radio>
              <Radio value="byok">Свой API-ключ (BYOK)</Radio>
              <Radio value="platform" disabled>
                Оплата в приложении (скоро)
              </Radio>
            </Radio.Group>
          </Form.Item>

          {llmMode === "byok" ? (
            <>
              {settings?.llm_key_configured ? (
                <Typography.Paragraph type="secondary">
                  Текущий ключ: <code>{settings.llm_key_preview}</code>
                </Typography.Paragraph>
              ) : (
                <Typography.Paragraph type="warning">
                  Укажите API-ключ провайдера для AI-сборки.
                </Typography.Paragraph>
              )}
              <Form.Item name="llm_api_key" label="API key">
                <Input.Password placeholder="sk-..." autoComplete="off" />
              </Form.Item>
              <Form.Item name="llm_base_url" label="Base URL">
                <Input placeholder="https://openai.api.proxyapi.ru/v1" />
              </Form.Item>
              <Form.Item name="llm_model" label="Модель">
                <Input placeholder="gemini/gemini-2.5-flash" />
              </Form.Item>
              <Typography.Paragraph type="secondary" className="text-xs">
                Из РФ удобнее{" "}
                <a href="https://proxyapi.ru" target="_blank" rel="noopener noreferrer">
                  ProxyAPI
                </a>
                .
              </Typography.Paragraph>
            </>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button type="primary" htmlType="submit" loading={saveMutation.isPending}>
              Сохранить
            </Button>
            {settings?.llm_key_configured && llmMode === "byok" ? (
              <Button danger loading={deleteMutation.isPending} onClick={() => deleteMutation.mutate()}>
                Удалить ключ
              </Button>
            ) : null}
            <Link to="/trips">
              <Button type="link">К прогулкам</Button>
            </Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
