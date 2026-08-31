import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Progress, Select, Space, Typography, notification } from "antd";
import { useEffect, useRef, useState } from "react";
import { getErrorMessage } from "../api/client";
import {
  fetchMyOsrmPrepares,
  fetchOsrmEligibleCities,
  fetchOsrmPrepareJob,
  startOsrmPrepare,
  type OsrmPrepareJob,
} from "../api/osrmPrepare";
import { resendVerification } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

const STAGE_LABEL: Record<string, string> = {
  queued: "В очереди",
  ensure_fo: "Проверка региона",
  extract: "Вырезка карты",
  poi: "Индекс мест",
  osrm: "Сборка графа OSRM",
  finalize: "Завершение",
};

function jobLabel(job: OsrmPrepareJob, names: Map<string, string>): string {
  return names.get(job.slug) ?? job.slug;
}

/** Одна строка на город: только последняя задача (старые failed не копятся). */
function latestJobsBySlug(jobs: OsrmPrepareJob[]): OsrmPrepareJob[] {
  const seen = new Set<string>();
  const out: OsrmPrepareJob[] = [];
  for (const job of jobs) {
    if (seen.has(job.slug)) continue;
    seen.add(job.slug);
    out.push(job);
  }
  return out;
}

function shortError(error: string | null | undefined, max = 120): string {
  if (!error) return "";
  const oneLine = error.replace(/\s+/g, " ").trim();
  if (oneLine.length <= max) return oneLine;
  return `${oneLine.slice(0, max - 1)}…`;
}

export function OsrmPreparePanel() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [slug, setSlug] = useState<string | undefined>();
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const notifiedRef = useRef<Set<string>>(new Set());

  const eligibleQuery = useQuery({
    queryKey: ["osrm-eligible"],
    queryFn: fetchOsrmEligibleCities,
  });

  const jobsQuery = useQuery({
    queryKey: ["osrm-prepares"],
    queryFn: fetchMyOsrmPrepares,
    refetchInterval: (q) => {
      const jobs = q.state.data?.jobs ?? [];
      return jobs.some((j) => j.status === "queued" || j.status === "running")
        ? 4000
        : false;
    },
  });

  const activeJobQuery = useQuery({
    queryKey: ["osrm-prepare", activeJobId],
    queryFn: () => fetchOsrmPrepareJob(activeJobId!),
    enabled: Boolean(activeJobId),
    refetchInterval: (q) => {
      const st = q.state.data?.status;
      return st === "queued" || st === "running" ? 3000 : false;
    },
  });

  useEffect(() => {
    const job = activeJobQuery.data;
    if (!job) return;
    if (job.status !== "succeeded" && job.status !== "failed") return;
    if (notifiedRef.current.has(job.id)) return;
    notifiedRef.current.add(job.id);
    const name =
      eligibleQuery.data?.cities.find((c) => c.slug === job.slug)?.display_name ??
      job.slug;
    if (job.status === "succeeded") {
      notification.success({
        title: "Город готов на карте",
        description: `«${name}» можно выбирать при сборке маршрута.`,
      });
      void queryClient.invalidateQueries({ queryKey: ["osrm-ready"] });
      void queryClient.invalidateQueries({ queryKey: ["osrm-eligible"] });
      void refreshUser?.();
    } else {
      notification.error({
        title: "Не удалось подготовить город",
        description: job.error || `«${name}» — попробуйте позже.`,
      });
      void refreshUser?.();
    }
    void jobsQuery.refetch();
  }, [activeJobQuery.data, eligibleQuery.data, queryClient, refreshUser, jobsQuery]);

  const startMutation = useMutation({
    mutationFn: (s: string) => startOsrmPrepare(s),
    onSuccess: (data) => {
      setActiveJobId(data.job.id);
      notification.info({
        title: data.joined ? "Уже готовится" : "Подготовка запущена",
        description: "Можно закрыть страницу — пришлём письмо по готовности.",
      });
      void jobsQuery.refetch();
      void refreshUser?.();
    },
    onError: (error) => {
      notification.error({
        title: "Не удалось запустить",
        description: getErrorMessage(error),
      });
    },
  });

  const resendMutation = useMutation({
    mutationFn: resendVerification,
    onSuccess: () => {
      notification.success({ title: "Письмо отправлено" });
    },
    onError: (error) => {
      notification.error({
        title: "Не удалось отправить",
        description: getErrorMessage(error),
      });
    },
  });

  const cities = eligibleQuery.data?.cities ?? [];
  const quotaUsed = user?.osrm_prepare_quota_used ?? jobsQuery.data?.quota_used ?? 0;
  const quotaLimit =
    user?.osrm_prepare_quota_limit ??
    jobsQuery.data?.quota_limit ??
    eligibleQuery.data?.quota_limit ??
    3;
  const remaining = Math.max(0, quotaLimit - quotaUsed);
  const activeJob = activeJobQuery.data;
  const nameMap = new Map(cities.map((c) => [c.slug, c.display_name]));

  if (user && user.email_verified === false) {
    return (
      <Card title="Города на карте (OSRM)" className="mb-4">
        <Alert
          type="warning"
          showIcon
          message="Подтвердите email"
          description="Чтобы добавлять города на карту, подтвердите адрес из письма после регистрации."
        />
        <Button
          className="mt-3"
          onClick={() => resendMutation.mutate()}
          loading={resendMutation.isPending}
        >
          Отправить письмо снова
        </Button>
      </Card>
    );
  }

  return (
    <Card title="Города на карте (OSRM)" className="mb-4">
      <Typography.Paragraph type="secondary" className="mb-3">
        Можно подготовить пеший граф для городов из каталога, если регион уже скачан на
        сервере. Лимит бесплатно: {quotaLimit} новых города (осталось {remaining}).
      </Typography.Paragraph>

      <Space.Compact className="mb-3 w-full max-w-md">
        <Select
          className="flex-1"
          showSearch
          placeholder={cities.length ? "Выберите город" : "Нет доступных городов"}
          optionFilterProp="label"
          value={slug}
          onChange={setSlug}
          options={cities.map((c) => ({
            value: c.slug,
            label: c.display_name,
          }))}
          disabled={!cities.length || startMutation.isPending}
        />
        <Button
          type="primary"
          disabled={!slug || remaining <= 0}
          loading={startMutation.isPending}
          onClick={() => slug && startMutation.mutate(slug)}
        >
          Подготовить
        </Button>
      </Space.Compact>

      {activeJob && (activeJob.status === "queued" || activeJob.status === "running") ? (
        <div className="mb-3">
          <Typography.Text>
            {jobLabel(activeJob, nameMap)} —{" "}
            {STAGE_LABEL[activeJob.stage] ?? activeJob.stage}
          </Typography.Text>
          <Progress percent={activeJob.progress} status="active" />
        </div>
      ) : null}

      {latestJobsBySlug(jobsQuery.data?.jobs ?? [])
        .slice(0, 5)
        .map((job) => (
          <div key={job.id} className="mb-1 text-sm text-slate-600">
            {jobLabel(job, nameMap)}: {job.status}
            {job.status === "failed" && job.error
              ? ` — ${shortError(job.error)}`
              : ""}
          </div>
        ))}
    </Card>
  );
}
