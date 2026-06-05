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
    <Space wrap>
      <Button type="primary" loading={loading} onClick={onApprove}>
        Утвердить программу
      </Button>
      <Button loading={loading} onClick={onRebuild}>
        Пересобрать
      </Button>
      <Button loading={loading} onClick={onSaveDraft}>
        Сохранить черновик
      </Button>
    </Space>
  );
}
