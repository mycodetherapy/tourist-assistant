import { useMutation } from "@tanstack/react-query";
import { Button, Form, Input, notification } from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage, isLlmKeyRequiredError } from "../api/client";
import type { RouteAnchor } from "../api/types";
import { createTrip } from "../api/trips";
import { NewTripAnchorFields } from "../components/NewTripAnchorFields";
import { OsrmCityChips, OsrmCityMatchBadge } from "../components/OsrmCityChips";
import { DEFAULT_USER_QUERY } from "../utils/preferences";

interface TripFormValues {
  city: string;
}

export function NewTripPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<TripFormValues>();
  const [routeAnchor, setRouteAnchor] = useState<RouteAnchor | null>(null);
  const city = Form.useWatch("city", form) ?? "";
  const cityReady = useMemo(() => city.trim().length > 0, [city]);

  useEffect(() => {
    if (!cityReady) {
      setRouteAnchor(null);
    }
  }, [cityReady]);

  const createMutation = useMutation({
    mutationFn: createTrip,
    onSuccess: (data) => {
      const url = data.run_id
        ? `/trips/${data.trip_id}?run=${data.run_id}`
        : `/trips/${data.trip_id}`;
      navigate(url);
    },
    onError: (error) => {
      if (isLlmKeyRequiredError(error)) {
        notification.warning({
          title: "Нужен ключ LLM",
          description:
            "Добавьте API-ключ в настройках, затем нажмите «Собрать программу» на странице прогулки.",
        });
        navigate("/settings");
        return;
      }
      notification.error({ title: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const handleSubmit = async () => {
    const values = await form.validateFields();

    if (!values.city?.trim()) {
      notification.error({
        title: "Ошибка",
        description: "Заполните город.",
      });
      return;
    }

    createMutation.mutate({
      city: values.city.trim(),
      user_query: DEFAULT_USER_QUERY,
      route_anchor: routeAnchor,
      start_run: true,
    });
  };

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold sm:mb-6 sm:text-2xl">Новая прогулка</h1>
      <Form form={form} layout="vertical" preserve className="max-w-2xl">
        <Form.Item name="city" label="Город маршрута" rules={[{ required: true }]}>
          <Input placeholder="Санкт-Петербург" suffix={<OsrmCityMatchBadge city={city} />} />
        </Form.Item>
        <OsrmCityChips
          selectedCity={city}
          onSelect={(name) => form.setFieldsValue({ city: name })}
        />
        <p className="mb-4 -mt-2 text-xs text-slate-500">
          Нет нужного города в списке?{" "}
          <Link to="/settings#osrm-cities" className="text-sky-700 underline-offset-2 hover:underline">
            Добавить город на карту в настройках
          </Link>
          {" "}
          (в бесплатном режиме — до 3 городов; со своим API-ключом без лимита).
        </p>
      </Form>

      <div className="relative max-w-2xl">
        <div
          className={cityReady ? undefined : "pointer-events-none select-none opacity-50"}
          aria-disabled={!cityReady}
        >
          <NewTripAnchorFields
            city={city}
            value={routeAnchor}
            onChange={setRouteAnchor}
            disabled={!cityReady}
          />

          <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:gap-3">
            <Button
              type="primary"
              block
              className="sm:!w-auto"
              loading={createMutation.isPending}
              disabled={!cityReady}
              onClick={handleSubmit}
            >
              Собрать маршруты
            </Button>
          </div>
        </div>

        {!cityReady && (
          <div
            className="absolute inset-0 z-10 rounded-lg bg-white/10"
            aria-hidden
          />
        )}
      </div>
    </div>
  );
}
