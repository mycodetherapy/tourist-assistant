import { Card, Spin, Steps } from "antd";

interface BuildingOverlayProps {
  visible: boolean;
  runStatus?: string;
  runScope?: "routes" | "full";
}

export function BuildingOverlay({ visible, runStatus, runScope = "full" }: BuildingOverlayProps) {
  if (!visible) return null;

  const step = runStatus === "queued" ? 0 : runScope === "routes" ? 1 : 0;

  return (
    <Card className="mb-6">
      <div className="flex flex-col items-center gap-4 py-6">
        <Spin size="large" />
        <p className="text-neutral-600 text-center max-w-md">
          Обновляем пул мест и формируем три варианта маршрута (A / B / C). Факт о
          городе подгрузится параллельно. Обычно 1–2 минуты.
        </p>
        <Steps
          current={step}
          className="max-w-lg w-full"
          items={[
            { title: "Пул мест (POI)" },
            { title: "Маршруты A/B/C" },
            { title: "Проверка маршрутов" },
          ]}
        />
      </div>
    </Card>
  );
}
