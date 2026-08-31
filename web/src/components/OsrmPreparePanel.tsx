import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Progress, Select, Space, Typography, notification } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { getErrorMessage } from "../api/client";
import {
  fetchMyOsrmPrepares,
  fetchOsrmEligibleCities,
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

const STATUS_LABEL: Record<string, string> = {
  queued: "в очереди",
  running: "готовится",
  succeeded: "готово",
  failed: "ошибка",
};

const WATCH_KEY = "osrm-prepare-watch";
const NOTIFIED_KEY = "osrm-prepare-notified";

function readIdSet(key: string): Set<string> {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

function writeIdSet(key: string, ids: Set<string>): void {
  try {
    sessionStorage.setItem(key, JSON.stringify([...ids]));
  } catch {
    /* ignore quota / private mode */
  }
}

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

function isInProgress(job: OsrmPrepareJob): boolean {
  return job.status === "queued" || job.status === "running";
}

export function OsrmPreparePanel() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [slug, setSlug] = useState<string | undefined>();
  const notifiedRef = useRef<Set<string>>(readIdSet(NOTIFIED_KEY));
  const watchRef = useRef<Set<string>>(readIdSet(WATCH_KEY));

  const eligibleQuery = useQuery({
    queryKey: ["osrm-eligible"],
    queryFn: fetchOsrmEligibleCities,
  });

  const jobsQuery = useQuery({
    queryKey: ["osrm-prepares"],
    queryFn: fetchMyOsrmPrepares,
    refetchInterval: (q) => {
      const jobs = q.state.data?.jobs ?? [];
      return jobs.some(isInProgress) ? 3000 : false;
    },
  });

  const cities = eligibleQuery.data?.cities ?? [];
  const nameMap = useMemo(
    () => new Map(cities.map((c) => [c.slug, c.display_name])),
    [cities],
  );
  const jobs = jobsQuery.data?.jobs ?? [];
  const inProgress = useMemo(() => jobs.filter(isInProgress), [jobs]);

  const watchJob = (id: string) => {
    watchRef.current.add(id);
    writeIdSet(WATCH_KEY, watchRef.current);
  };

  // Следим за queued/running (в т.ч. после возврата на страницу) и тостим финал.
  useEffect(() => {
    if (!jobsQuery.isSuccess) return;
    let watchChanged = false;
    let notifiedChanged = false;

    for (const job of jobs) {
      if (isInProgress(job)) {
        if (!watchRef.current.has(job.id)) {
          watchRef.current.add(job.id);
          watchChanged = true;
        }
        continue;
      }
      if (job.status !== "succeeded" && job.status !== "failed") continue;
      if (!watchRef.current.has(job.id)) continue;
      if (notifiedRef.current.has(job.id)) {
        watchRef.current.delete(job.id);
        watchChanged = true;
        continue;
      }

      notifiedRef.current.add(job.id);
      watchRef.current.delete(job.id);
      notifiedChanged = true;
      watchChanged = true;

      const name = nameMap.get(job.slug) ?? job.slug;
      if (job.status === "succeeded") {
        notification.success({
          title: "Город готов на карте",
          description: `«${name}» можно выбирать при сборке маршрута.`,
        });
        void queryClient.invalidateQueries({ queryKey: ["osrm-ready"] });
        void queryClient.invalidateQueries({ queryKey: ["osrm-eligible"] });
      } else {
        notification.error({
          title: "Не удалось подготовить город",
          description: shortError(job.error) || `«${name}» — попробуйте позже.`,
        });
      }
      void refreshUser?.();
    }

    if (watchChanged) writeIdSet(WATCH_KEY, watchRef.current);
    if (notifiedChanged) writeIdSet(NOTIFIED_KEY, notifiedRef.current);
  }, [jobs, jobsQuery.isSuccess, nameMap, queryClient, refreshUser]);

  const startMutation = useMutation({
    mutationFn: (s: string) => startOsrmPrepare(s),
    onSuccess: (data) => {
      watchJob(data.job.id);
      notification.info({
        title: data.joined ? "Уже готовится" : "Подготовка запущена",
        description:
          "Можно закрыть страницу — прогресс сохранится. По готовности покажем уведомление в приложении.",
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

  const quotaUsed = user?.osrm_prepare_quota_used ?? jobsQuery.data?.quota_used ?? 0;
  const quotaLimit =
    user?.osrm_prepare_quota_limit ??
    jobsQuery.data?.quota_limit ??
    eligibleQuery.data?.quota_limit ??
    3;
  const remaining = Math.max(0, quotaLimit - quotaUsed);

  if (user && user.email_verified === false) {
    return (
      <Card id="osrm-cities" title="Города на карте (OSRM)" className="mb-4 scroll-mt-20">
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
    <Card id="osrm-cities" title="Города на карте (OSRM)" className="mb-4 scroll-mt-20">
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
          disabled={!slug || remaining <= 0 || inProgress.length > 0}
          loading={startMutation.isPending}
          onClick={() => slug && startMutation.mutate(slug)}
          title={
            inProgress.length > 0
              ? "Дождитесь окончания текущей подготовки"
              : undefined
          }
        >
          Подготовить
        </Button>
      </Space.Compact>

      {inProgress.map((job) => (
        <div key={job.id} className="mb-3">
          <Typography.Text>
            {jobLabel(job, nameMap)} — {STAGE_LABEL[job.stage] ?? job.stage}
          </Typography.Text>
          <Progress
            percent={job.progress}
            status="active"
            size="small"
          />
        </div>
      ))}

      {latestJobsBySlug(jobs)
        .slice(0, 5)
        .map((job) => (
          <div key={job.id} className="mb-1 text-sm text-slate-600">
            {jobLabel(job, nameMap)}: {STATUS_LABEL[job.status] ?? job.status}
            {job.status === "failed" && job.error
              ? ` — ${shortError(job.error)}`
              : ""}
          </div>
        ))}
    </Card>
  );
}
