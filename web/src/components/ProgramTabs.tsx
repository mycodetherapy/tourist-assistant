import { Tabs } from "antd";
import ReactMarkdown from "react-markdown";
import type { FinalProgram } from "../api/types";

interface ProgramTabsProps {
  program: FinalProgram;
}

const SECTIONS: { key: keyof FinalProgram; label: string }[] = [
  { key: "tickets", label: "Билеты" },
  { key: "events", label: "Мероприятия" },
  { key: "dining", label: "Питание" },
  { key: "lifehacks", label: "Лайфхаки" },
];

export function ProgramTabs({ program }: ProgramTabsProps) {
  return (
    <Tabs
      items={SECTIONS.map(({ key, label }) => ({
        key,
        label,
        children: (
          <div className="prose max-w-none whitespace-pre-wrap">
            <ReactMarkdown
              components={{
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {program[key]}
            </ReactMarkdown>
          </div>
        ),
      }))}
    />
  );
}
