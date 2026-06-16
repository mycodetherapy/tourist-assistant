import { Button } from "antd";
import type { TripRouteCase } from "../api/routeTypes";

interface RouteCaseSwitcherProps {
  cases: TripRouteCase[];
  value: string;
  onChange: (caseId: string) => void;
  className?: string;
}

/** Переключатель вариантов A/B/C (мобильная вкладка «Маршруты»). */
export function RouteCaseSwitcher({
  cases,
  value,
  onChange,
  className,
}: RouteCaseSwitcherProps) {
  if (cases.length <= 1) {
    return null;
  }
  return (
    <div className={`mt-3 flex flex-wrap gap-2 ${className ?? ""}`.trim()}>
      {cases.map((routeCase) => {
        const caseId = String(routeCase.case_id);
        const selected = value === caseId;
        return (
          <Button
            key={caseId}
            type={selected ? "primary" : "default"}
            size="small"
            className="!m-0 shrink-0"
            onClick={() => onChange(caseId)}
          >
            Вариант {routeCase.case_id}
          </Button>
        );
      })}
    </div>
  );
}
