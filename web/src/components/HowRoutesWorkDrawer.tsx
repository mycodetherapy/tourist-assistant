import { QuestionCircleOutlined } from "@ant-design/icons";
import { Button, Drawer, Typography } from "antd";
import { useState } from "react";
import { FREE_VS_LLM, HOW_ROUTES_WORK_SECTIONS } from "../content/buildModes";

type HowRoutesWorkDrawerProps = {
  /** Компактная текстовая ссылка вместо кнопки */
  link?: boolean;
  className?: string;
};

export function HowRoutesWorkDrawer({ link = false, className }: HowRoutesWorkDrawerProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {link ? (
        <button
          type="button"
          className={`inline-flex items-center gap-1 border-0 bg-transparent p-0 text-sky-700 underline decoration-sky-300 underline-offset-2 hover:text-sky-900 ${className ?? ""}`}
          onClick={() => setOpen(true)}
        >
          <QuestionCircleOutlined />
          Как собираются маршруты
        </button>
      ) : (
        <Button
          type="link"
          className={className}
          icon={<QuestionCircleOutlined />}
          onClick={() => setOpen(true)}
        >
          Как собираются маршруты
        </Button>
      )}
      <Drawer
        title="Как собираются маршруты"
        placement="right"
        width={400}
        open={open}
        onClose={() => setOpen(false)}
      >
        <Typography.Paragraph type="secondary" className="mb-4">
          {FREE_VS_LLM.shortCompare}
        </Typography.Paragraph>
        <div className="space-y-4">
          {HOW_ROUTES_WORK_SECTIONS.map((section) => (
            <section key={section.title}>
              <Typography.Title level={5} className="!mb-1">
                {section.title}
              </Typography.Title>
              <Typography.Paragraph className="!mb-0 text-slate-600">
                {section.body}
              </Typography.Paragraph>
            </section>
          ))}
        </div>
        <Typography.Paragraph type="secondary" className="mt-6 mb-0 text-xs">
          {FREE_VS_LLM.cityPackHint}
        </Typography.Paragraph>
      </Drawer>
    </>
  );
}
