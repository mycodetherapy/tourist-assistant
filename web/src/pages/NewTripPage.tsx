import { useMutation, useQuery } from "@tanstack/react-query";
import { Button, Form, Input, Steps, notification } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import type { TripPreferences } from "../api/types";
import { createTrip, fetchProfile } from "../api/trips";
import { LaunchSummary } from "../components/LaunchSummary";
import {
  DEFAULT_PREFERENCES,
  PreferencesForm,
} from "../components/PreferencesForm";
import { normalizeTripPreferences } from "../utils/preferences";

interface TripFormValues {
  city: string;
  dates: string;
  origin_city: string;
  user_query: string;
}

export function NewTripPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [tripForm] = Form.useForm<TripFormValues>();
  const [prefsForm] = Form.useForm<TripPreferences>();
  const [useSavedProfile, setUseSavedProfile] = useState(false);
  const [savedPrefs, setSavedPrefs] = useState<TripPreferences | null>(null);
  const [tripDraft, setTripDraft] = useState<TripFormValues | null>(null);
  const [prefsDraft, setPrefsDraft] = useState<TripPreferences | null>(null);

  const profileQuery = useQuery({
    queryKey: ["profile"],
    queryFn: fetchProfile,
  });

  useEffect(() => {
    if (profileQuery.data?.preferences) {
      const normalized = normalizeTripPreferences(profileQuery.data.preferences);
      setSavedPrefs(normalized);
      prefsForm.setFieldsValue(normalized);
      setUseSavedProfile(true);
    }
  }, [profileQuery.data, prefsForm]);

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
    if (step === 0) {
      const values = await tripForm.validateFields();
      setTripDraft(values);
      setStep(1);
      return;
    }
    if (step === 1) {
      const rawPrefs =
        useSavedProfile && savedPrefs ? savedPrefs : await prefsForm.validateFields();
      setPrefsDraft(normalizeTripPreferences(rawPrefs));
      setStep(2);
    }
  };

  const handleSubmit = async () => {
    const tripValues = tripDraft ?? (await tripForm.validateFields());
    const prefsRaw =
      useSavedProfile && savedPrefs
        ? savedPrefs
        : prefsDraft ?? normalizeTripPreferences(await prefsForm.validateFields());

    if (!tripValues.city?.trim() || !tripValues.dates?.trim()) {
      notification.error({
        title: "Ошибка",
        description: "Заполните город и даты на шаге «Маршрут».",
      });
      setStep(0);
      return;
    }

    createMutation.mutate({
      city: tripValues.city.trim(),
      dates: tripValues.dates.trim(),
      origin_city: tripValues.origin_city?.trim() || "Москва",
      user_query:
        tripValues.user_query?.trim() || "Составь культурную программу поездки",
      preferences: normalizeTripPreferences(prefsRaw),
      start_run: true,
    });
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Новая поездка</h1>
      <Steps
        current={step}
        className="mb-8"
        items={[
          { title: "Маршрут" },
          { title: "Предпочтения" },
          { title: "Запуск" },
        ]}
      />

      {step === 0 && (
        <Form
          form={tripForm}
          layout="vertical"
          preserve
          initialValues={{
            origin_city: "Москва",
            user_query: "Составь культурную программу поездки",
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
          <Form.Item name="user_query" label="Ваш запрос">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      )}

      {step === 1 && (
        <Form
          form={prefsForm}
          layout="vertical"
          preserve
          initialValues={DEFAULT_PREFERENCES}
          className="max-w-lg"
        >
          <PreferencesForm
            initialValues={savedPrefs ?? undefined}
            useSavedProfile={useSavedProfile}
            onUseSavedProfileChange={setUseSavedProfile}
          />
        </Form>
      )}

      {step === 2 && tripDraft && prefsDraft && (
        <LaunchSummary
          city={tripDraft.city}
          dates={tripDraft.dates}
          originCity={tripDraft.origin_city?.trim() || "Москва"}
          preferences={prefsDraft}
        />
      )}

      <div className="mt-6 flex gap-3">
        {step > 0 && <Button onClick={() => setStep((s) => s - 1)}>Назад</Button>}
        {step < 2 && (
          <Button type="primary" onClick={handleNext}>
            Далее
          </Button>
        )}
        {step === 2 && (
          <Button type="primary" loading={createMutation.isPending} onClick={handleSubmit}>
            Собрать программу
          </Button>
        )}
      </div>
    </div>
  );
}
