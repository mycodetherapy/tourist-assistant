import { CloseOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { APP_NAME } from "../brand";
import { initYandexMetrika } from "../utils/analytics";
import {
  type CookieConsentValue,
  getCookieConsent,
  setCookieConsent,
} from "../utils/cookieConsent";

export function CookieConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (getCookieConsent() === null) {
      setVisible(true);
      return;
    }
    initYandexMetrika();
  }, []);

  const choose = (value: CookieConsentValue) => {
    setCookieConsent(value);
    setVisible(false);
    if (value === "accepted") {
      initYandexMetrika();
    }
  };

  if (!visible) return null;

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-[1100] border-t border-slate-200 bg-white p-4 shadow-[0_-4px_24px_rgba(15,23,42,0.12)] sm:p-5 relative"
      role="dialog"
      aria-label="Согласие на использование файлов cookie"
    >
      <Button
        type="text"
        size="small"
        icon={<CloseOutlined />}
        aria-label="Закрыть — только необходимые cookie"
        className="!absolute !right-2 !top-2 text-slate-500 hover:!text-slate-800"
        onClick={() => choose("necessary")}
      />
      <div className="mx-auto flex max-w-5xl flex-col gap-4 pr-8 sm:flex-row sm:items-end sm:justify-between sm:pr-10">
        <div className="min-w-0 flex-1 text-sm leading-relaxed text-slate-700">
          <p className="mb-1 font-semibold text-slate-900">{APP_NAME} и файлы cookie</p>
          <p className="m-0">
            Мы используем необходимые cookie для работы сайта (сессия, безопасность). С вашего
            согласия подключаем{" "}
            <a
              href="https://yandex.ru/legal/metrica_termsofuse/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sky-700 underline"
            >
              Яндекс.Метрику
            </a>{" "}
            (аналитика, в т.ч. вебвизор). Подробнее — в{" "}
            <Link to="/privacy#cookies" className="text-sky-700 underline">
              Политике конфиденциальности
            </Link>
            .
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
          <Button onClick={() => choose("necessary")}>Только необходимые</Button>
          <Button type="primary" onClick={() => choose("accepted")}>
            Принять все
          </Button>
        </div>
      </div>
    </div>
  );
}
