import { UserAddOutlined } from "@ant-design/icons";
import { Button, Modal, Typography } from "antd";
import { Link } from "react-router-dom";

interface RegisterGateModalProps {
  open: boolean;
  message?: string;
  returnTo?: string;
  onClose: () => void;
  onRegisterClick?: () => void;
}

export function RegisterGateModal({
  open,
  message = "Зарегистрируйтесь, чтобы сохранить прогулку и продолжить работу с маршрутами",
  returnTo,
  onClose,
  onRegisterClick,
}: RegisterGateModalProps) {
  const registerHref = returnTo
    ? `/register?return=${encodeURIComponent(returnTo)}`
    : "/register";

  return (
    <Modal
      open={open}
      title="Нужна регистрация"
      onCancel={onClose}
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <Button onClick={onClose}>Позже</Button>
          <Link
            to={registerHref}
            className="inline-flex"
            onClick={() => {
              onRegisterClick?.();
              onClose();
            }}
          >
            <Button type="primary" icon={<UserAddOutlined />}>
              Зарегистрироваться
            </Button>
          </Link>
        </div>
      }
    >
      <Typography.Paragraph className="!mb-0">{message}</Typography.Paragraph>
    </Modal>
  );
}
