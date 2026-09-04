import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Radio, Spin, Typography, notification } from "antd";
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { deleteLlmKey, fetchSettings, updateSettings } from "../api/settings";
import type { LlmMode, UpdateSettingsPayload } from "../api/types";
import { HowRoutesWorkDrawer } from "../components/HowRoutesWorkDrawer";
import { OsrmPreparePanel } from "../components/OsrmPreparePanel";
import { FREE_VS_LLM } from "../content/buildModes";
import { useAuth } from "../auth/AuthContext";

type SettingsFormValues = UpdateSettingsPayload & { llm_mode: LlmMode };

export function SettingsPage() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const { refreshUser } = useAuth();
  const [form] = Form.useForm<SettingsFormValues>();
  const watchedMode = Form.useWatch("llm_mode", form);

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  useEffect(() => {
    if (settingsQuery.isLoading) return;
    if (location.hash !== "#osrm-cities") return;
    const el = document.getElementById("osrm-cities");
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [location.hash, settingsQuery.isLoading]);

  const saveMutation = useMutation({
    mutationFn: (values: SettingsFormValues) => {
      const payload: UpdateSettingsPayload = {
        llm_mode: values.llm_mode,
        llm_base_url: values.llm_base_url,
        llm_model: values.llm_model,
      };
      const key = values.llm_api_key?.trim();
      if (key) {
        payload.llm_api_key = key;
      }
      return updateSettings(payload);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], data);
      void queryClient.invalidateQueries({ queryKey: ["osrm-prepares"] });
      void refreshUser?.();
      notification.success({ title: "Настройки сохранены" });
      form.setFieldValue("llm_api_key", "");
      if (data.llm_mode === "byok" && data.llm_key_configured) {
        window.setTimeout(() => {
          document.getElementById("osrm-cities")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        }, 50);
      }
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
      void queryClient.invalidateQueries({ queryKey: ["osrm-prepares"] });
      void refreshUser?.();
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
      <OsrmPreparePanel />
      <Alert
        className="mb-4"
        type="info"
        showIcon
        message="Режим сборки маршрутов"
        description={
          <>
            <p className="m-0 mb-2">
              <strong>Бесплатно</strong> — маршруты строит алгоритм на основе пула мест из Wikipedia (до 30 сборок в сутки).
            </p>
            <p className="m-0 mb-2">
              <strong>Свой API-ключ (BYOK)</strong> — LLM помогает с формулировками маршрутов и
              справками. Если город загружен на сервер — расширенный справочник мест (обычно больше
              точек). Оплата — у провайдера (ProxyAPI, OpenRouter). Ориентир одной AI-сборки: ~
              {settings?.estimated_ai_run_cost_rub ?? 10} ₽.
            </p>
            <p className="m-0 text-xs text-slate-600">{FREE_VS_LLM.cityPackHint}</p>
            <p className="m-0 mt-2">
              <HowRoutesWorkDrawer link />
            </p>
          </>
        }
      />
      <Card id="ai-mode">
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
              <Form.Item
                name="llm_api_key"
                label="API key"
                extra={
                  settings?.llm_key_configured
                    ? "Оставьте пустым, чтобы оставить текущий ключ."
                    : undefined
                }
              >
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
