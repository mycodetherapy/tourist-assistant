import { Segmented } from "antd";
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
    <Segmented
      className={className ?? "routes-case-select mb-3"}
      value={value}
      onChange={(next) => onChange(String(next))}
      options={cases.map((routeCase) => ({
        label: `Вариант ${routeCase.case_id}`,
        value: String(routeCase.case_id),
      }))}
    />
  );
}
