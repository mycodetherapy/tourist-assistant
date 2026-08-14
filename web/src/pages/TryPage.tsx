import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Form, Input, notification } from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import {
  ensureGuestSession,
  getCaptchaErrorMessage,
  getRegisterRequiredMessage,
  guestCreateTrip,
  isCaptchaError,
  isRegisterRequiredError,
} from "../api/guest";
import type { RouteAnchor } from "../api/types";
import { RegisterGateModal } from "../components/RegisterGateModal";
import { LegalConsentFields } from "../components/LegalConsentFields";
import { NewTripAnchorFields } from "../components/NewTripAnchorFields";
import { useGuestSmartCaptcha } from "../hooks/useGuestSmartCaptcha";
import { SMART_CAPTCHA_CONTAINER_CLASS } from "../hooks/useYandexSmartCaptcha";
import { DEFAULT_USER_QUERY } from "../utils/preferences";
import { HowRoutesWorkDrawer } from "../components/HowRoutesWorkDrawer";
import { FREE_VS_LLM } from "../content/buildModes";
import { METRIKA_GOALS, reachGoal } from "../utils/analytics";

interface TripFormValues {
  city: string;
  accept_terms: boolean;
  accept_privacy: boolean;
}

export function TryPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<TripFormValues>();
  const [routeAnchor, setRouteAnchor] = useState<RouteAnchor | null>(null);
  const [registerGateOpen, setRegisterGateOpen] = useState(false);
  const [registerGateMessage, setRegisterGateMessage] = useState<string>();
  const city = Form.useWatch("city", form) ?? "";
  const cityReady = useMemo(() => city.trim().length > 0, [city]);
  const captcha = useGuestSmartCaptcha();

  useEffect(() => {
    reachGoal(METRIKA_GOALS.TRY_PAGE_VIEW);
    void ensureGuestSession().catch(() => {});
  }, []);

  useEffect(() => {
    if (!cityReady) {
      setRouteAnchor(null);
    }
  }, [cityReady]);

  const createMutation = useMutation({
    mutationFn: guestCreateTrip,
    onSuccess: (data) => {
      reachGoal(METRIKA_GOALS.TRY_TRIP_CREATED, { trip_id: data.trip_id });
      const url = data.run_id
        ? `/try/${data.trip_id}?run=${data.run_id}`
        : `/try/${data.trip_id}`;
      navigate(url);
    },
    onError: (error) => {
      if (isRegisterRequiredError(error)) {
        setRegisterGateMessage(getRegisterRequiredMessage(error) ?? undefined);
        setRegisterGateOpen(true);
        reachGoal(METRIKA_GOALS.GUEST_REGISTER_GATE, { source: "try_create" });
        return;
      }
      if (isCaptchaError(error)) {
        notification.error({
          title: "Проверка CAPTCHA",
          description: getCaptchaErrorMessage(error) ?? undefined,
        });
        return;
      }
      notification.error({ title: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (!values.city?.trim()) {
      notification.error({ title: "Ошибка", description: "Заполните город." });
      return;
    }
    let captcha_token: string | undefined;
    if (captcha.enabled) {
      try {
        captcha_token = await captcha.requestToken();
      } catch (err) {
        notification.error({
          title: "Проверка CAPTCHA",
          description: err instanceof Error ? err.message : "Не удалось пройти проверку",
        });
        return;
      }
    }
    createMutation.mutate({
      city: values.city.trim(),
      user_query: DEFAULT_USER_QUERY,
      route_anchor: routeAnchor,
      start_run: true,
      captcha_token,
    });
  };

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:py-12">
      <div className="mb-6">
        <h1 className="mb-2 text-2xl font-semibold sm:text-3xl">Маршрут без регистрации</h1>
        <p className="text-slate-600">
          Укажите город и соберите прогулку — одна сборка и один пересбор. Чтобы сохранить маршрут и
          открыть новые города,{" "}
          <Link
            to="/register?return=/try"
            className="text-sky-700 underline"
            onClick={() => reachGoal(METRIKA_GOALS.GUEST_REGISTER_CLICK, { source: "try_page" })}
          >
            создайте аккаунт
          </Link>
          .
        </p>
      </div>

      <Alert
        type="info"
        showIcon
        className="mb-6"
        title="Без аккаунта"
        description={
          <div className="space-y-2">
            <p className="m-0">
              Одна полная сборка и один пересбор. Новый город или дополнительные пересборы — после
              регистрации.
            </p>
            <p className="m-0">{FREE_VS_LLM.guestHint}</p>
            <HowRoutesWorkDrawer link />
          </div>
        }
      />

      <Form form={form} layout="vertical" preserve initialValues={{ accept_terms: false, accept_privacy: false }}>
        <Form.Item name="city" label="Город маршрута" rules={[{ required: true }]}>
          <Input placeholder="Санкт-Петербург" />
        </Form.Item>
        <LegalConsentFields hint="Согласие нужно для гостевой сборки: сессия, город, точка старта и технические логи." />
      </Form>

      <div className="relative">
        <div
          className={cityReady ? undefined : "pointer-events-none select-none opacity-50"}
          aria-disabled={!cityReady}
        >
          <NewTripAnchorFields
            city={city}
            value={routeAnchor}
            onChange={setRouteAnchor}
            disabled={!cityReady}
            guestMode
          />

          <div className="mt-6 flex flex-col gap-2 sm:flex-row">
            <Button
              type="primary"
              block
              className="sm:!w-auto"
            loading={createMutation.isPending}
            disabled={!cityReady}
            onClick={() => void handleSubmit()}
            >
              Собрать маршруты
            </Button>
            <Link to="/login">
              <Button block className="sm:!w-auto">
                Уже есть аккаунт
              </Button>
            </Link>
          </div>
        </div>
      </div>

      <div ref={captcha.containerRef} className={SMART_CAPTCHA_CONTAINER_CLASS} aria-hidden="true" />

      <RegisterGateModal
        open={registerGateOpen}
        message={registerGateMessage}
        returnTo="/try"
        onClose={() => setRegisterGateOpen(false)}
        onRegisterClick={() =>
          reachGoal(METRIKA_GOALS.GUEST_REGISTER_CLICK, { source: "try_gate_modal" })
        }
      />
    </div>
  );
}
