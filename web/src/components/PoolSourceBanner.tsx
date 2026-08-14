import { QuestionCircleOutlined } from "@ant-design/icons";
import { Tooltip, Typography } from "antd";
import {
  parsePoolCount,
  parsePoolProvider,
  providerLabel,
  providerTooltip,
} from "../content/buildModes";

type PoolSourceBannerProps = {
  /** Строка вида «Пул: 89 мест досуга (osm). …» */
  summary?: string | null;
};

export function PoolSourceBanner({ summary }: PoolSourceBannerProps) {
  const raw = (summary || "").trim();
  if (!raw) return null;

  const count = parsePoolCount(raw);
  const provider = parsePoolProvider(raw);
  const label = providerLabel(provider);
  const tip = providerTooltip(provider);

  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
      <span>
        {count != null ? (
          <>
            Пул: <strong>{count}</strong> мест · источник: <strong>{label}</strong>
          </>
        ) : (
          <>
            Источник мест: <strong>{label}</strong>
          </>
        )}
      </span>
      <Tooltip title={tip}>
        <Typography.Text type="secondary" className="inline-flex cursor-help items-center gap-1 text-xs">
          <QuestionCircleOutlined />
          что это
        </Typography.Text>
      </Tooltip>
    </div>
  );
}
