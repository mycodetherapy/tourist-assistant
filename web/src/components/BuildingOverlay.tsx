import { Card, Spin, Steps } from "antd";

interface BuildingOverlayProps {
  visible: boolean;
  runStatus?: string;
}

export function BuildingOverlay({ visible, runStatus }: BuildingOverlayProps) {
  if (!visible) return null;

  const step = runStatus === "queued" ? 0 : 1;

  return (
    <Card className="mb-6">
      <div className="flex flex-col items-center gap-4 py-6">
        <Spin size="large" />
        <p className="text-neutral-600 text-center max-w-md">
          Собираем билеты, ищем места на Яндекс.Картах и формируем три варианта маршрута
          (A / B / C). Обычно 1–2 минуты.
        </p>
        <Steps
          current={step}
          className="max-w-lg w-full"
          items={[
            { title: "Билеты и POI" },
            { title: "Маршруты A/B/C" },
            { title: "Проверка" },
          ]}
        />
      </div>
    </Card>
  );
}
