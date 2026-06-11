import { useMutation } from "@tanstack/react-query";
import { Button, Form, Grid, Input, Select, Steps, notification } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import type { TripPreferences } from "../api/types";
import { createTrip } from "../api/trips";
import { LaunchSummary } from "../components/LaunchSummary";
import {
  DEFAULT_USER_QUERY,
  normalizeTripPreferences,
} from "../utils/preferences";

interface TripFormValues {
  city: string;
  dates: string;
  origin_city: string;
  travel_party: TripPreferences["travel_party"];
}

const { useBreakpoint } = Grid;

export function NewTripPage() {
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const isMobile = !screens.sm;
  const [step, setStep] = useState(0);
  const [form] = Form.useForm<TripFormValues>();
  const [draft, setDraft] = useState<{
    trip: TripFormValues;
    preferences: TripPreferences;
  } | null>(null);

  const createMutation = useMutation({
    mutationFn: createTrip,
    onSuccess: (data) => {
      const url = data.run_id
        ? `/trips/${data.trip_id}?run=${data.run_id}`
        : `/trips/${data.trip_id}`;
      navigate(url);
    },
    onError: (error) => {
      notification.error({ title: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const handleNext = async () => {
    const values = await form.validateFields();
    setDraft({
      trip: values,
      preferences: normalizeTripPreferences({ travel_party: values.travel_party }),
    });
    setStep(1);
  };

  const handleSubmit = async () => {
    const current =
      draft ??
      (() => {
        const values = form.getFieldsValue(true) as TripFormValues;
        return {
          trip: values,
          preferences: normalizeTripPreferences({ travel_party: values.travel_party }),
        };
      })();

    if (!current.trip.city?.trim() || !current.trip.dates?.trim()) {
      notification.error({
        title: "Ошибка",
        description: "Заполните город и даты.",
      });
      setStep(0);
      return;
    }

    createMutation.mutate({
      city: current.trip.city.trim(),
      dates: current.trip.dates.trim(),
      origin_city: current.trip.origin_city?.trim() || "Москва",
      user_query: DEFAULT_USER_QUERY,
      preferences: current.preferences,
      start_run: true,
    });
  };

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold sm:mb-6 sm:text-2xl">Новая поездка</h1>
      <Steps
        current={step}
        direction={isMobile ? "vertical" : "horizontal"}
        className="mb-6 sm:mb-8"
        items={[{ title: "Поездка" }, { title: "Запуск" }]}
      />

      {step === 0 && (
        <Form
          form={form}
          layout="vertical"
          preserve
          initialValues={{
            origin_city: "Москва",
            travel_party: "couple",
          }}
          className="max-w-lg"
        >
          <Form.Item name="city" label="Город поездки" rules={[{ required: true }]}>
            <Input placeholder="Санкт-Петербург" />
          </Form.Item>
          <Form.Item name="dates" label="Даты" rules={[{ required: true }]}>
            <Input placeholder="1-4 августа 2026" />
          </Form.Item>
          <Form.Item name="origin_city" label="Город вылета">
            <Input />
          </Form.Item>
          <Form.Item
            name="travel_party"
            label="Состав группы"
            extra="Влияет на число пассажиров в ссылках на билеты"
            rules={[{ required: true }]}
          >
            <Select
              options={[
                { value: "solo", label: "1 взрослый" },
                { value: "couple", label: "2 взрослых" },
                { value: "parent_child", label: "1 взрослый + 1 ребёнок" },
                { value: "family", label: "2 взрослых + 1 ребёнок" },
                { value: "family_two", label: "2 взрослых + 2 ребёнка" },
                { value: "friends", label: "3 взрослых" },
              ]}
            />
          </Form.Item>
        </Form>
      )}

      {step === 1 && draft && (
        <LaunchSummary
          city={draft.trip.city}
          dates={draft.trip.dates}
          originCity={draft.trip.origin_city?.trim() || "Москва"}
          preferences={draft.preferences}
        />
      )}

      <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:gap-3">
        {step > 0 && (
          <Button block className="sm:!w-auto" onClick={() => setStep(0)}>
            Назад
          </Button>
        )}
        {step === 0 && (
          <Button type="primary" block className="sm:!w-auto" onClick={handleNext}>
            Далее
          </Button>
        )}
        {step === 1 && (
          <Button
            type="primary"
            block
            className="sm:!w-auto"
            loading={createMutation.isPending}
            onClick={handleSubmit}
          >
            Собрать программу
          </Button>
        )}
      </div>
    </div>
  );
}
