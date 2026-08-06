import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Typography, notification } from "antd";
import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import type { RebuildScope } from "../api/types";
import {
  fetchGuestSession,
  getCaptchaErrorMessage,
  getRegisterRequiredMessage,
  guestFetchProgram,
  guestFetchRun,
  guestFetchTrip,
  guestStartRun,
  isCaptchaError,
  isRegisterRequiredError,
} from "../api/guest";
import { parseRouteProgram } from "../api/routeTypes";
import { BuildingOverlay } from "../components/BuildingOverlay";
import { ProgramTabs } from "../components/ProgramTabs";
import { RegisterGateModal } from "../components/RegisterGateModal";
import { TripAnchorCard } from "../components/TripAnchorCard";
import { TripMetaCard } from "../components/TripMetaCard";
import { useGuestSmartCaptcha } from "../hooks/useGuestSmartCaptcha";
import { SMART_CAPTCHA_CONTAINER_CLASS } from "../hooks/useYandexSmartCaptcha";
import { METRIKA_GOALS, reachGoal } from "../utils/analytics";

export function GuestTripDetailPage() {
  const { id } = useParams();
  const tripId = Number(id);
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeRunId, setActiveRunId] = useState<string | null>(searchParams.get("run"));
  const [activeRunScope, setActiveRunScope] = useState<"routes" | "full">(
    searchParams.get("scope") === "routes" ? "routes" : "full",
  );
  const [lastBuildError, setLastBuildError] = useState<string | null>(null);
  const [registerGateOpen, setRegisterGateOpen] = useState(false);
  const [registerGateMessage, setRegisterGateMessage] = useState<string>();
  const sawRunInProgressRef = useRef(false);
  const queryClient = useQueryClient();
  const captcha = useGuestSmartCaptcha();

  const sessionQuery = useQuery({
    queryKey: ["guest", "session"],
    queryFn: fetchGuestSession,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const tripQuery = useQuery({
    queryKey: ["guest", "trips", tripId],
    queryFn: () => guestFetchTrip(tripId),
    enabled: tripId > 0,
  });

  const runQuery = useQuery({
    queryKey: ["guest", "runs", activeRunId],
    queryFn: () => guestFetchRun(activeRunId!),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "queued" || status === "running") {
        return 2000;
      }
      return false;
    },
  });

  const runInProgress =
    !!activeRunId &&
    (runQuery.isLoading ||
      runQuery.data?.status === "queued" ||
      runQuery.data?.status === "running");

  const isBuilding = runInProgress;

  const programQuery = useQuery({
    queryKey: ["guest", "trips", tripId, "program"],
    queryFn: () => guestFetchProgram(tripId),
    enabled: tripId > 0 && !runInProgress,
    retry: false,
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: (query) => {
      if (query.state.status === "error") return false;
      const status = query.state.data?.city_fact_status;
      if (status === "pending") return 2500;
      return false;
    },
  });

  const rebuildMutation = useMutation({
    mutationFn: ({ scope, captcha_token }: { scope: RebuildScope; captcha_token?: string }) =>
      guestStartRun(tripId, scope, captcha_token),
    onSuccess: (data, { scope }) => {
      if (data.run_id) {
        setLastBuildError(null);
        setActiveRunId(data.run_id);
        setSearchParams({ run: data.run_id, scope });
      }
      void sessionQuery.refetch();
      queryClient.invalidateQueries({ queryKey: ["guest", "trips", tripId] });
    },
    onError: (error) => {
      if (isRegisterRequiredError(error)) {
        setRegisterGateMessage(getRegisterRequiredMessage(error) ?? undefined);
        setRegisterGateOpen(true);
        return;
      }
      if (isCaptchaError(error)) {
        notification.error({
          title: "Проверка CAPTCHA",
          description: getCaptchaErrorMessage(error) ?? undefined,
        });
        return;
      }
      notification.error({ title: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const startGuestRun = async (scope: RebuildScope) => {
    let captcha_token: string | undefined;
    if (captcha.enabled) {
      try {
        captcha_token = await captcha.requestToken();
      } catch (err) {
        notification.error({
          title: "Проверка CAPTCHA",
          description: err instanceof Error ? err.message : "Не удалось пройти проверку",
        });
        return;
      }
    }
    setActiveRunScope(scope);
    rebuildMutation.mutate({ scope, captcha_token });
  };

  const session = sessionQuery.data;
  const canPartialRebuild =
    session != null && session.partial_runs_used < session.partial_runs_limit;
  const canFullRebuild =
    session != null && session.full_runs_used < session.full_runs_limit;

  useEffect(() => {
    const paramRun = searchParams.get("run");
    const paramScope = searchParams.get("scope");
    if (paramRun) setActiveRunId(paramRun);
    if (paramScope === "routes" || paramScope === "full") {
      setActiveRunScope(paramScope);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!activeRunId || !runQuery.isError) return;
    const error = runQuery.error;
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      setActiveRunId(null);
      setSearchParams({}, { replace: true });
      queryClient.removeQueries({ queryKey: ["guest", "runs", activeRunId] });
    }
  }, [activeRunId, runQuery.isError, runQuery.error, queryClient, setSearchParams]);

  useEffect(() => {
    const status = runQuery.data?.status;
    if (status === "queued" || status === "running") {
      sawRunInProgressRef.current = true;
    }
    if (status === "completed" || status === "failed") {
      if (status === "completed" && sawRunInProgressRef.current) {
        notification.success({ title: "Готово" });
        reachGoal(METRIKA_GOALS.TRY_BUILD_SUCCESS, {
          trip_id: tripId,
          scope: activeRunScope,
        });
      }
      sawRunInProgressRef.current = false;
      setSearchParams({}, { replace: true });
      setActiveRunId(null);
      setActiveRunScope("full");
      void sessionQuery.refetch();
      queryClient.invalidateQueries({ queryKey: ["guest", "trips", tripId] });
      queryClient.invalidateQueries({ queryKey: ["guest", "trips", tripId, "program"] });
      if (status === "failed" && runQuery.data?.error) {
        setLastBuildError(runQuery.data.error);
        notification.error({
          title: "Ошибка сборки",
          description: runQuery.data.error,
        });
      }
    }
  }, [runQuery.data, tripId, queryClient, setSearchParams, sessionQuery]);

  if (tripQuery.isLoading) {
    return <div className="p-4">Загрузка…</div>;
  }

  if (!tripQuery.data) {
    return (
      <Alert
        type="error"
        className="m-4"
        title="Прогулка не найдена"
        description={
          <Link to="/try" className="underline">
            Собрать новую прогулку
          </Link>
        }
      />
    );
  }

  const trip = tripQuery.data;
  const hasProgram = !!programQuery.data;
  const programSettled = !programQuery.isLoading;
  const canRebuild = hasProgram && !isBuilding;
  const canStartBuild = programSettled && !hasProgram && !isBuilding;

  const openRegisterGate = (message?: string) => {
    setRegisterGateMessage(message);
    setRegisterGateOpen(true);
    reachGoal(METRIKA_GOALS.GUEST_REGISTER_GATE, {
      trip_id: tripId,
      message: message ?? null,
    });
  };

  const trackGuestRegisterClick = (source: string) => {
    reachGoal(METRIKA_GOALS.GUEST_REGISTER_CLICK, { trip_id: tripId, source });
  };

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 px-3 py-4 sm:px-4 sm:py-6">
      <Alert
        type="warning"
        showIcon
        title="Без аккаунта"
        description={
          <span>
            Чтобы сохранить прогулку и собирать новые города,{" "}
            <Link
              to={`/register?return=${encodeURIComponent(`/try/${tripId}`)}`}
              className="font-medium underline"
              onClick={() => trackGuestRegisterClick("banner_link")}
            >
              зарегистрируйтесь
            </Link>
            . Осталось:{" "}
            {session
              ? `${Math.max(0, session.partial_runs_limit - session.partial_runs_used)} пересбор(ов)`
              : "…"}
          </span>
        }
        action={
          <Link
            to={`/register?return=${encodeURIComponent(`/try/${tripId}`)}`}
            onClick={() => trackGuestRegisterClick("banner_button")}
          >
            <Button size="small" type="primary">
              Регистрация
            </Button>
          </Link>
        }
      />

      <TripMetaCard trip={trip} guestMode />

      {lastBuildError && !isBuilding && !hasProgram ? (
        <Alert type="error" showIcon title="Сборка маршрутов не удалась" description={lastBuildError} />
      ) : null}

      {!isBuilding && programQuery.data?.data_warnings?.length ? (
        <Alert
          type="warning"
          showIcon
          title="Ограничения данных"
          description={programQuery.data.data_warnings.join(" ")}
        />
      ) : null}

      {!isBuilding && (
        <TripAnchorCard
          tripId={tripId}
          city={trip.city}
          routeCases={
            programQuery.data ? parseRouteProgram(programQuery.data.program.routes) : []
          }
          guestMode
        />
      )}

      <BuildingOverlay
        visible={isBuilding}
        runStatus={runQuery.data?.status}
        runScope={activeRunScope}
      />

      {canStartBuild && canFullRebuild && (
        <Card title="Сборка маршрутов">
          <Button
            type="primary"
            loading={rebuildMutation.isPending}
            onClick={() => void startGuestRun("full")}
          >
            Собрать маршруты
          </Button>
        </Card>
      )}

      {canRebuild && (
        <Card title="Пересбор маршрутов">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
            {canPartialRebuild ? (
              <Button
                type="primary"
                loading={rebuildMutation.isPending}
                onClick={() => void startGuestRun("routes")}
              >
                Пересобрать маршруты
              </Button>
            ) : (
              <Button
                type="primary"
                onClick={() =>
                  openRegisterGate("Пересбор маршрутов доступен после регистрации")
                }
              >
                Пересобрать маршруты
              </Button>
            )}
            {canFullRebuild ? (
              <Button
                type="dashed"
                loading={rebuildMutation.isPending}
                onClick={() => void startGuestRun("full")}
              >
                Глубокий пересбор
              </Button>
            ) : (
              <Button
                type="dashed"
                onClick={() =>
                  openRegisterGate("Глубокий пересбор доступен после регистрации")
                }
              >
                Глубокий пересбор
              </Button>
            )}
          </div>
          <Typography.Text className="mt-2 block text-gray-500" style={{ fontSize: 12 }}>
            Без аккаунта доступен один пересбор маршрутов без повторного поиска мест.
          </Typography.Text>
        </Card>
      )}

      {programQuery.isLoading && !isBuilding && <div>Загрузка программы…</div>}

      {programQuery.data && !isBuilding && (
        <Card
          className="program-card"
          title={`Программа v${programQuery.data.version} (${programQuery.data.scope})`}
        >
          <ProgramTabs
            tripId={tripId}
            city={trip.city}
            data={programQuery.data}
            guestMode
            votingDisabled={isBuilding}
          />
        </Card>
      )}

      {!hasProgram && programSettled && !isBuilding && !canStartBuild && (
        <Empty description="Программа ещё не сформирована" />
      )}

      <RegisterGateModal
        open={registerGateOpen}
        message={registerGateMessage}
        returnTo={`/try/${tripId}`}
        onClose={() => setRegisterGateOpen(false)}
        onRegisterClick={() => trackGuestRegisterClick("gate_modal")}
      />

      <div ref={captcha.containerRef} className={SMART_CAPTCHA_CONTAINER_CLASS} aria-hidden="true" />
    </div>
  );
}
