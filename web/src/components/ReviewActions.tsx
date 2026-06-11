import { Button, Space } from "antd";

interface ReviewActionsProps {
  loading?: boolean;
  onApprove: () => void;
  onSaveDraft: () => void;
  onRebuild: () => void;
}

export function ReviewActions({
  loading,
  onApprove,
  onSaveDraft,
  onRebuild,
}: ReviewActionsProps) {
  return (
    <Space wrap className="w-full [&_.ant-space-item]:w-full sm:[&_.ant-space-item]:w-auto">
      <Button type="primary" block className="sm:!w-auto" loading={loading} onClick={onApprove}>
        Утвердить программу
      </Button>
      <Button block className="sm:!w-auto" loading={loading} onClick={onRebuild}>
        Пересобрать
      </Button>
      <Button block className="sm:!w-auto" loading={loading} onClick={onSaveDraft}>
        Сохранить черновик
      </Button>
    </Space>
  );
}
