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
        <p className="text-neutral-600">
          Собираем программу… Обычно это занимает 1–2 минуты.
        </p>
        <Steps
          current={step}
          className="max-w-lg w-full"
          items={[
            { title: "Поиск данных" },
            { title: "Сборка программы" },
            { title: "Проверка" },
          ]}
        />
      </div>
    </Card>
  );
}
