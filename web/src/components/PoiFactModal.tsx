import { Alert, Modal, Spin } from "antd";
import ReactMarkdown from "react-markdown";
import type { PoiFactResponse } from "../api/poiFacts";
import { markdownExternalLinkComponents } from "./markdownExternalLink";

interface PoiFactModalProps {
  open: boolean;
  title: string;
  loading: boolean;
  error: string | null;
  data: PoiFactResponse | null;
  onClose: () => void;
}

export function PoiFactModal({
  open,
  title,
  loading,
  error,
  data,
  onClose,
}: PoiFactModalProps) {
  return (
    <Modal
      open={open}
      title={title}
      footer={null}
      onCancel={onClose}
      destroyOnHidden
      width={560}
      classNames={{ body: "max-h-[calc(60vh+76px)] overflow-y-auto" }}
    >
      {loading ? (
        <div className="flex min-h-[120px] items-center justify-center py-6">
          <Spin tip="Собираем справку…" />
        </div>
      ) : error ? (
        <Alert type="warning" showIcon title="Справка недоступна" description={error} />
      ) : data?.text ? (
        <div className="prose max-w-none text-sm leading-relaxed text-gray-800">
          <ReactMarkdown components={markdownExternalLinkComponents}>{data.text}</ReactMarkdown>
        </div>
      ) : (
        <Alert type="info" showIcon title="Нет данных" description="Попробуйте открыть точку позже." />
      )}
    </Modal>
  );
}
