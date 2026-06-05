import { Select } from "antd";
import type { RebuildScope } from "../api/types";

const SCOPES: { value: RebuildScope; label: string }[] = [
  { value: "full", label: "Всю программу" },
  { value: "tickets", label: "Только билеты" },
  { value: "events", label: "Только мероприятия" },
  { value: "dining", label: "Только питание" },
  { value: "lifehacks", label: "Только лайфхаки" },
];

interface RebuildScopeSelectProps {
  value: RebuildScope;
  onChange: (value: RebuildScope) => void;
}

export function RebuildScopeSelect({ value, onChange }: RebuildScopeSelectProps) {
  return (
    <Select
      value={value}
      onChange={onChange}
      options={SCOPES}
      className="min-w-[220px]"
    />
  );
}
