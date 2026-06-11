import { Grid, Select } from "antd";
import type { RebuildScope } from "../api/types";

const { useBreakpoint } = Grid;

const SCOPES: { value: RebuildScope; label: string }[] = [
  { value: "full", label: "Всю программу" },
  { value: "tickets", label: "Только билеты" },
  { value: "routes", label: "Только маршруты" },
  { value: "lifehacks", label: "Только лайфхаки" },
];

interface RebuildScopeSelectProps {
  value: RebuildScope;
  onChange: (value: RebuildScope) => void;
}

export function RebuildScopeSelect({ value, onChange }: RebuildScopeSelectProps) {
  const screens = useBreakpoint();
  const isMobile = screens.md === false;
  const normalized = value === "events" || value === "dining" ? "routes" : value;
  return (
    <Select
      value={normalized}
      onChange={onChange}
      options={SCOPES}
      className="rebuild-scope-select w-full sm:min-w-[220px] sm:w-56"
      styles={
        isMobile
          ? {
              content: {
                display: "flex",
                justifyContent: "center",
                textAlign: "center",
              },
            }
          : undefined
      }
    />
  );
}
