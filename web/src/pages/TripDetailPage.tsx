import { DeleteOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Popconfirm, Space, notification } from "antd";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import type { RebuildScope, ReviewAction } from "../api/types";
import { deleteTrip, fetchPreferences, startRun, submitReview } from "../api/trips";
import { BuildingOverlay } from "../components/BuildingOverlay";
import { ProgramTabs } from "../components/ProgramTabs";
import { RebuildScopeSelect } from "../components/RebuildScopeSelect";
import { ReviewActions } from "../components/ReviewActions";
import { TripMetaCard } from "../components/TripMetaCard";
import { LEISURE_LABELS } from "../utils/leisure";
import { normalizeLeisureCategories } from "../utils/preferences";
import { useRunPolling } from "../hooks/useRunPolling";
import { useTrip, useTripProgram } from "../hooks/useTrip";

export function TripDetailPage() {
  const { id } = useParams();
  const tripId = Number(id);
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeRunId, setActiveRunId] = useState<string | null>(
    searchParams.get("run"),
  );
  const [rebuildScope, setRebuildScope] = useState<RebuildScope>("full");
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const tripQuery = useTrip(tripId);
  const prefsQuery = useQuery({
    queryKey: ["trips", tripId, "preferences"],
    queryFn: () => fetchPreferences(tripId),
    enabled: Number.isFinite(tripId),
  });
  const runQuery = useRunPolling(activeRunId);

  const reviewMutation = useMutation({
    mutationFn: (action: ReviewAction) => submitReview(tripId, action),
    onSuccess: (data) => {
      if (data.run_id) {
        setActiveRunId(data.run_id);
        setSearchParams({ run: data.run_id });
      }
      queryClient.invalidateQueries({ queryKey: ["trips", tripId] });
      queryClient.invalidateQueries({ queryKey: ["trips", tripId, "program"] });
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      notification.success({ message: "Готово" });
    },
    onError: (error) => {
      notification.error({ message: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteTrip(tripId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      notification.success({ message: "Поездка удалена" });
      navigate("/");
    },
    onError: (error) => {
      notification.error({ message: "Ошибка", description: getErrorMessage(error) });
    },
  });

  const rebuildMutation = useMutation({
    mutationFn: () => startRun(tripId, rebuildScope),
    onSuccess: (data) => {
      if (data.run_id) {
        setActiveRunId(data.run_id);
        setSearchParams({ run: data.run_id });
      }
      queryClient.invalidateQueries({ queryKey: ["trips", tripId] });
    },
    onError: (error) => {
      notification.error({ message: "Ошибка", description: getErrorMessage(error) });
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
    if (paramRun) setActiveRunId(paramRun);
  }, [searchParams]);

  useEffect(() => {
    if (runQuery.data?.status === "completed" || runQuery.data?.status === "failed") {
      setSearchParams({}, { replace: true });
      setActiveRunId(null);
      queryClient.invalidateQueries({ queryKey: ["trips", tripId] });
      queryClient.invalidateQueries({ queryKey: ["trips", tripId, "program"] });
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      if (runQuery.data.status === "failed" && runQuery.data.error) {
        notification.error({
          message: "Ошибка сборки",
          description: runQuery.data.error,
        });
      }
    }
  }, [runQuery.data, tripId, queryClient, setSearchParams]);

  if (tripQuery.isLoading) {
    return <div>Загрузка…</div>;
  }

  if (!tripQuery.data) {
    return <Alert type="error" message="Поездка не найдена" />;
  }

  const trip = tripQuery.data;
  const showReview = trip.status === "review" && !isBuilding;
  const canRebuild = (trip.status === "review" || trip.status === "approved") && !isBuilding;

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Popconfirm
          title={`Удалить поездку #${trip.id}?`}
          description={`${trip.city}, ${trip.dates}`}
          okText="Удалить"
          cancelText="Отмена"
          okButtonProps={{ danger: true }}
          onConfirm={() => deleteMutation.mutate()}
          disabled={isBuilding}
        >
          <Button
            danger
            icon={<DeleteOutlined />}
            loading={deleteMutation.isPending}
            disabled={isBuilding}
          >
            Удалить поездку
          </Button>
        </Popconfirm>
      </div>

      <TripMetaCard trip={trip} />

      {prefsQuery.data && (
        <Alert
          type="info"
          showIcon
          className="mb-0"
          message="Категории досуга для этой поездки"
          description={
            <span>
              {normalizeLeisureCategories(prefsQuery.data.leisure_categories)
                .map((tag) => LEISURE_LABELS[tag])
                .join(", ")}
            </span>
          }
        />
      )}

      <BuildingOverlay visible={isBuilding} runStatus={runQuery.data?.status} />

      {showReview && (
        <Card title="Утверждение программы">
          <ReviewActions
            loading={reviewMutation.isPending}
            onApprove={() => reviewMutation.mutate("approve")}
            onSaveDraft={() => reviewMutation.mutate("save_draft")}
            onRebuild={() => reviewMutation.mutate("rebuild")}
          />
        </Card>
      )}

      {canRebuild && (
        <Card title="Частичный пересбор">
          <Space>
            <RebuildScopeSelect value={rebuildScope} onChange={setRebuildScope} />
            <Button
              loading={rebuildMutation.isPending}
              onClick={() => rebuildMutation.mutate()}
            >
              Пересобрать раздел
            </Button>
          </Space>
        </Card>
      )}

      {programQuery.isLoading && !isBuilding && <div>Загрузка программы…</div>}

      {programQuery.data && !isBuilding && (
        <Card
          title={`Программа v${programQuery.data.version} (${programQuery.data.scope})`}
        >
          <ProgramTabs
            tripId={tripId}
            data={programQuery.data}
            votingDisabled={isBuilding}
          />
        </Card>
      )}

      {!programQuery.data && !programQuery.isLoading && !isBuilding && (
        <Empty description="Программа ещё не сформирована" />
      )}
    </div>
  );
}
