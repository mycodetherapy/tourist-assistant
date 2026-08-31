import { DeleteOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Grid, Popconfirm, Typography, notification } from "antd";
import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { getErrorMessage, isLlmKeyRequiredError } from "../api/client";
import type { RebuildScope } from "../api/types";
import { deleteTrip, startRun } from "../api/trips";
import { parseRouteProgram } from "../api/routeTypes";
import { BuildingOverlay } from "../components/BuildingOverlay";
import { HowRoutesWorkDrawer } from "../components/HowRoutesWorkDrawer";
import { ProgramTabs } from "../components/ProgramTabs";
import { TripAnchorCard } from "../components/TripAnchorCard";
import { TripMetaCard } from "../components/TripMetaCard";
import { OsrmGraphUpdateBanner } from "../components/OsrmGraphUpdateBanner";
import { FREE_VS_LLM } from "../content/buildModes";
import { useRunPolling } from "../hooks/useRunPolling";
import { useTrip, useTripProgram } from "../hooks/useTrip";

const { useBreakpoint } = Grid;

export function TripDetailPage() {
  const { id } = useParams();
  const tripId = Number(id);
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeRunId, setActiveRunId] = useState<string | null>(
    searchParams.get("run"),
  );
  const [activeRunScope, setActiveRunScope] = useState<"routes" | "full">(
    searchParams.get("scope") === "routes" ? "routes" : "full",
  );
  const [lastBuildError, setLastBuildError] = useState<string | null>(null);
  const sawRunInProgressRef = useRef(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const isMobile = screens.md === false;

  const tripQuery = useTrip(tripId);
  const runQuery = useRunPolling(activeRunId);

  const deleteMutation = useMutation({
    mutationFn: () => deleteTrip(tripId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      notification.success({ title: "Прогулка удалена" });
      navigate("/trips");
    },
    onError: (error) => {
      notification.error({ title: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const rebuildMutation = useMutation({
    mutationFn: (scope: RebuildScope) => startRun(tripId, scope),
    onSuccess: (data, scope) => {
      if (data.run_id) {
        setLastBuildError(null);
        setActiveRunId(data.run_id);
        setSearchParams({ run: data.run_id, scope });
      }
      queryClient.invalidateQueries({ queryKey: ["trips", tripId] });
    },
    onError: (error) => {
      if (isLlmKeyRequiredError(error)) {
        notification.warning({
          title: "Нужен ключ LLM",
          description: "Добавьте API-ключ в настройках, затем запустите сборку снова.",
        });
        navigate("/settings");
        return;
      }
      notification.error({ title: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const runInProgress =
    !!activeRunId &&
    (runQuery.isLoading ||
      runQuery.data?.status === "queued" ||
      runQuery.data?.status === "running");

  const isBuilding = runInProgress || rebuildMutation.isPending;

  const programQuery = useTripProgram(tripId, !runInProgress);

  useEffect(() => {
    const paramRun = searchParams.get("run");
    const paramScope = searchParams.get("scope");
    if (paramRun) setActiveRunId(paramRun);
    if (paramScope === "routes" || paramScope === "full") {
      setActiveRunScope(paramScope);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!activeRunId || !runQuery.isError) {
      return;
    }
    const error = runQuery.error;
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      setActiveRunId(null);
      setSearchParams({}, { replace: true });
      queryClient.removeQueries({ queryKey: ["runs", activeRunId] });
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
      }
      sawRunInProgressRef.current = false;
      setSearchParams({}, { replace: true });
      setActiveRunId(null);
      setActiveRunScope("full");
      queryClient.invalidateQueries({ queryKey: ["trips", tripId] });
      queryClient.invalidateQueries({ queryKey: ["trips", tripId, "program"] });
      queryClient.invalidateQueries({ queryKey: ["trip-osrm-update", tripId] });
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      if (status === "failed" && runQuery.data?.error) {
        setLastBuildError(runQuery.data.error);
        notification.error({
          title: "Ошибка сборки",
          description: runQuery.data.error,
        });
      }
    }
  }, [runQuery.data, tripId, queryClient, setSearchParams]);

  if (tripQuery.isLoading) {
    return <div>Загрузка…</div>;
  }

  if (!tripQuery.data) {
    return <Alert type="error" title="Прогулка не найдена" />;
  }

  const trip = tripQuery.data;
  const hasProgram = !!programQuery.data;
  const programSettled = !programQuery.isLoading;
  const canRebuild = hasProgram && !isBuilding;
  const canStartBuild = programSettled && !hasProgram && !isBuilding;

  return (
    <div className="space-y-6">
      <div className="flex justify-stretch sm:justify-end">
        <Popconfirm
          title={`Удалить прогулку #${trip.id}?`}
          description={trip.city}
          okText="Удалить"
          cancelText="Отмена"
          okButtonProps={{ danger: true }}
          onConfirm={() => deleteMutation.mutate()}
          disabled={isBuilding}
        >
          <Button
            danger
            block
            className="sm:!w-auto"
            icon={<DeleteOutlined />}
            loading={deleteMutation.isPending}
            disabled={isBuilding}
          >
            Удалить прогулку
          </Button>
        </Popconfirm>
      </div>

      <TripMetaCard trip={trip} />

      {lastBuildError && !isBuilding && !hasProgram ? (
        <Alert
          type="error"
          showIcon
          title="Сборка маршрутов не удалась"
          description={lastBuildError}
          action={
            lastBuildError.includes("настройках") || lastBuildError.includes("LLM") ? (
              <Button size="small" onClick={() => navigate("/settings")}>
                Настройки
              </Button>
            ) : undefined
          }
        />
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
        />
      )}

      <BuildingOverlay
        visible={isBuilding}
        runStatus={runQuery.data?.status}
        runScope={activeRunScope}
      />

      {canStartBuild && (
        <Card title="Сборка маршрутов">
          <Alert
            type="info"
            showIcon
            className="mb-4"
            title="Маршруты ещё не собраны"
            description="Нажмите кнопку ниже — агент сгенерирует маршруты (1–2 минуты). Факт о городе подгрузится отдельно."
          />
          <Button
            type="primary"
            block
            className="sm:!w-auto"
            loading={rebuildMutation.isPending}
            onClick={() => {
              setActiveRunScope("full");
              rebuildMutation.mutate("full");
            }}
          >
            Собрать маршруты
          </Button>
        </Card>
      )}

      {canRebuild && (
        <OsrmGraphUpdateBanner
          tripId={tripId}
          hasRoutes={hasProgram}
          rebuilding={rebuildMutation.isPending}
          onRebuildRoutes={() => {
            setActiveRunScope("routes");
            rebuildMutation.mutate("routes");
          }}
        />
      )}

      {canRebuild && (
        <Card title="Пересбор маршрутов">
          {isMobile ? (
            <div className="space-y-2">
              <Button
                type="primary"
                block
                loading={rebuildMutation.isPending}
              onClick={() => {
                setActiveRunScope("routes");
                rebuildMutation.mutate("routes");
              }}
              >
                Пересобрать маршруты
              </Button>
              <Button
                block
                type="dashed"
                loading={rebuildMutation.isPending}
              onClick={() => {
                setActiveRunScope("full");
                rebuildMutation.mutate("full");
              }}
              >
                Глубокий пересбор
              </Button>
              <Typography.Text
                className="block text-gray-500"
                style={{ fontSize: 12, lineHeight: "16px" }}
              >
                {FREE_VS_LLM.rebuildRoutesHint}{" "}
                <HowRoutesWorkDrawer link />
              </Typography.Text>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="primary"
                loading={rebuildMutation.isPending}
                onClick={() => rebuildMutation.mutate("routes")}
              >
                Пересобрать маршруты
              </Button>
              <Button
                type="dashed"
                loading={rebuildMutation.isPending}
                onClick={() => rebuildMutation.mutate("full")}
              >
                Глубокий пересбор
              </Button>
              <Typography.Text
                className="text-gray-500"
                style={{ fontSize: 12, lineHeight: "16px" }}
              >
                {FREE_VS_LLM.rebuildRoutesHint}{" "}
                <HowRoutesWorkDrawer link />
              </Typography.Text>
            </div>
          )}
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
            votingDisabled={isBuilding}
          />
        </Card>
      )}

      {!hasProgram && programSettled && !isBuilding && !canStartBuild && (
        <Empty description="Программа ещё не сформирована" />
      )}
    </div>
  );
}
