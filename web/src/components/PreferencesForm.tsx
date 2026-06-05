import { Checkbox, Form, Input, InputNumber, Select } from "antd";
import type { TripPreferences } from "../api/types";

export const DEFAULT_PREFERENCES: TripPreferences = {
  pace: "moderate",
  budget: "medium",
  interests: ["музеи", "архитектура", "выставки"],
  cuisine: "любая местная",
  min_restaurant_rating: 4.5,
  transport_preference: "mixed",
  travel_party: "couple",
  special_notes: "",
};

interface PreferencesFormProps {
  initialValues?: TripPreferences;
  useSavedProfile: boolean;
  onUseSavedProfileChange: (value: boolean) => void;
}

export function PreferencesForm({
  initialValues,
  useSavedProfile,
  onUseSavedProfileChange,
}: PreferencesFormProps) {
  return (
    <>
      {initialValues && (
        <Checkbox
          checked={useSavedProfile}
          onChange={(e) => onUseSavedProfileChange(e.target.checked)}
          className="mb-4"
        >
          Использовать сохранённый профиль без изменений
        </Checkbox>
      )}
      <Form.Item name="pace" label="Темп поездки" rules={[{ required: true }]}>
        <Select
          disabled={useSavedProfile}
          options={[
            { value: "relaxed", label: "Спокойно — 1–2 объекта в день" },
            { value: "moderate", label: "Умеренно — 2–3 объекта" },
            { value: "packed", label: "Насыщенно — максимум впечатлений" },
          ]}
        />
      </Form.Item>
      <Form.Item name="budget" label="Бюджет" rules={[{ required: true }]}>
        <Select
          disabled={useSavedProfile}
          options={[
            { value: "economy", label: "Эконом" },
            { value: "medium", label: "Средний" },
            { value: "unlimited", label: "Без жёстких ограничений" },
          ]}
        />
      </Form.Item>
      <Form.Item name="interests" label="Интересы">
        <Select
          mode="tags"
          disabled={useSavedProfile}
          placeholder="музеи, архитектура, выставки"
          tokenSeparators={[","]}
        />
      </Form.Item>
      <Form.Item name="cuisine" label="Кухня">
        <Input disabled={useSavedProfile} />
      </Form.Item>
      <Form.Item name="min_restaurant_rating" label="Мин. рейтинг ресторанов">
        <InputNumber disabled={useSavedProfile} min={1} max={5} step={0.1} className="w-full" />
      </Form.Item>
      <Form.Item name="transport_preference" label="Передвижение" rules={[{ required: true }]}>
        <Select
          disabled={useSavedProfile}
          options={[
            { value: "metro", label: "Метро и общтранспорт" },
            { value: "walking", label: "В основном пешком" },
            { value: "taxi", label: "Такси" },
            { value: "mixed", label: "Метро + пешком" },
          ]}
        />
      </Form.Item>
      <Form.Item name="travel_party" label="Состав группы" rules={[{ required: true }]}>
        <Select
          disabled={useSavedProfile}
          options={[
            { value: "solo", label: "Один/одна" },
            { value: "couple", label: "Пара" },
            { value: "family", label: "С детьми" },
            { value: "friends", label: "Компания друзей" },
          ]}
        />
      </Form.Item>
      <Form.Item name="special_notes" label="Доп. пожелания">
        <Input.TextArea disabled={useSavedProfile} rows={2} />
      </Form.Item>
    </>
  );
}
