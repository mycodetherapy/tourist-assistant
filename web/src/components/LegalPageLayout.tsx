import { CompassOutlined } from "@ant-design/icons";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  APP_DOMAIN,
  APP_NAME,
  LEGAL_EFFECTIVE_DATE,
  LEGAL_VERSION,
  OPERATOR_EMAIL,
  OPERATOR_NAME,
} from "../brand";

interface LegalPageLayoutProps {
  title: string;
  children: ReactNode;
}

export function LegalPageLayout({ title, children }: LegalPageLayoutProps) {
  return (
    <div className="min-h-dvh bg-[#f8fafc] text-slate-800">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold text-[#001529] no-underline">
            <CompassOutlined className="text-xl text-sky-600" />
            <span>{APP_NAME}</span>
          </Link>
          <nav className="flex flex-wrap gap-3 text-sm">
            <Link to="/terms" className="text-sky-700 no-underline hover:underline">
              Соглашение
            </Link>
            <Link to="/privacy" className="text-sky-700 no-underline hover:underline">
              Конфиденциальность
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
        <h1 className="mb-2 text-2xl font-bold text-[#001529] sm:text-3xl">{title}</h1>
        <p className="mb-8 text-sm text-slate-500">
          Версия {LEGAL_VERSION} · действует с {LEGAL_EFFECTIVE_DATE} · {APP_DOMAIN}
        </p>
        <div className="legal-prose space-y-4 text-sm leading-relaxed text-slate-700 sm:text-base">
          {children}
        </div>
      </main>

      <footer className="border-t border-slate-200 bg-white px-4 py-6 text-sm text-slate-500 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <p className="m-0">
            Оператор: {OPERATOR_NAME} (физическое лицо). Связь:{" "}
            <a href={`mailto:${OPERATOR_EMAIL}`} className="text-sky-700 underline">
              {OPERATOR_EMAIL}
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}

export function LegalSection({
  id,
  title,
  children,
}: {
  id?: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20">
      <h2 className="mb-2 text-lg font-semibold text-[#001529] sm:text-xl">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
