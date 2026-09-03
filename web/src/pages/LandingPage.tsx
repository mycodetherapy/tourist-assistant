import {
  CompassOutlined,
  EnvironmentOutlined,
  KeyOutlined,
  LoginOutlined,
  SafetyOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import { Button } from "antd";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { APP_DESCRIPTION, APP_DOMAIN, APP_HERO, APP_NAME, APP_TAGLINE } from "../brand";
import { HowRoutesWorkDrawer } from "../components/HowRoutesWorkDrawer";
import { LANDING_FEATURES, LANDING_H1, LANDING_HOW_INTRO, LANDING_STEPS } from "../content/landing";
import { METRIKA_GOALS, reachGoal } from "../utils/analytics";

export function LandingPage() {
  useEffect(() => {
    reachGoal(METRIKA_GOALS.LANDING_VIEW);
  }, []);

  return (
    <div className="landing min-h-dvh bg-[#f8fafc] text-slate-800">
      <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold text-[#001529] no-underline">
            <CompassOutlined className="text-xl text-sky-600" />
            <span>{APP_NAME}</span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link to="/login" onClick={() => reachGoal(METRIKA_GOALS.CTA_LOGIN_CLICK)}>
              <Button icon={<LoginOutlined />}>Войти</Button>
            </Link>
            <Link to="/register" onClick={() => reachGoal(METRIKA_GOALS.CTA_REGISTER_CLICK)}>
              <Button type="primary" icon={<UserAddOutlined />}>
                Регистрация
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="landing-hero relative overflow-hidden px-4 pb-16 pt-12 sm:px-6 sm:pb-24 sm:pt-20">
        <div className="landing-hero-glow pointer-events-none absolute inset-0" aria-hidden />
        <div className="relative mx-auto max-w-6xl">
          <p className="mb-3 text-sm font-medium uppercase tracking-wider text-sky-700">
            {APP_DOMAIN} · {APP_TAGLINE.toLowerCase()}
          </p>
          <h1 className="mb-5 max-w-3xl text-3xl font-bold leading-tight text-[#001529] sm:text-4xl lg:text-5xl">
            {LANDING_H1}
          </h1>
          <p className="mb-8 max-w-2xl text-base leading-relaxed text-slate-600 sm:text-lg">
            <strong className="font-semibold text-slate-800">{APP_NAME}</strong> — {APP_HERO}
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/try" onClick={() => reachGoal(METRIKA_GOALS.CTA_TRY_CLICK)}>
              <Button type="primary" size="large" icon={<UserAddOutlined />}>
                Собрать маршрут
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <h2 className="mb-3 text-2xl font-bold text-[#001529] sm:text-3xl">Зачем {APP_NAME}</h2>
          <p className="mb-10 max-w-2xl text-slate-600">{APP_DESCRIPTION}</p>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {LANDING_FEATURES.map((item) => (
              <article
                key={item.title}
                className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 shadow-sm transition hover:border-sky-200 hover:shadow-md"
              >
                <h3 className="mb-2 text-lg font-semibold text-[#001529]">{item.title}</h3>
                <p className="m-0 text-sm leading-relaxed text-slate-600">{item.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <h2 className="mb-3 text-2xl font-bold text-[#001529] sm:text-3xl">Как это работает</h2>
          <p className="mb-10 max-w-2xl text-slate-600">{LANDING_HOW_INTRO}</p>
          <ol className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {LANDING_STEPS.map((step, index) => (
              <li
                key={step.title}
                className="relative rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <span className="mb-3 inline-flex h-8 w-8 items-center justify-center rounded-full bg-sky-100 text-sm font-bold text-sky-700">
                  {index + 1}
                </span>
                <h3 className="mb-2 text-base font-semibold text-[#001529]">{step.title}</h3>
                <p className="m-0 text-sm leading-relaxed text-slate-600">{step.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-slate-200 bg-white px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <h2 className="mb-3 text-2xl font-bold text-[#001529] sm:text-3xl">Что нужно для старта</h2>
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 p-6 sm:p-8">
              <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[#001529]">
                <UserAddOutlined className="text-sky-600" />
                Аккаунт на {APP_DOMAIN}
              </h3>
              <ul className="m-0 list-none space-y-3 p-0 text-slate-600">
                <li className="flex gap-2">
                  <span className="text-sky-600">•</span>
                  <span>
                    Можно{" "}
                    <Link to="/try" className="font-medium text-sky-700 underline" onClick={() => reachGoal(METRIKA_GOALS.CTA_TRY_CLICK)}>
                      собрать маршрут без регистрации
                    </Link>
                    ; аккаунт — чтобы сохранить прогулку и собирать новые города.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-sky-600">•</span>
                  <span>Регистрация по email и паролю или вход через Google.</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-sky-600">•</span>
                  <span>Прогулки и версии маршрутов хранятся в вашем личном кабинете.</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-sky-600">•</span>
                  <span>
                    <EnvironmentOutlined className="mr-1 text-sky-600" />
                    Чтобы подставить текущее местоположение при выборе стартовой точки, открывайте сайт по HTTPS (в т.ч. с телефона).
                  </span>
                </li>
              </ul>
              <div className="mt-6">
                <Link to="/register" onClick={() => reachGoal(METRIKA_GOALS.CTA_REGISTER_CLICK)}>
                  <Button type="primary">Зарегистрироваться</Button>
                </Link>
              </div>
            </div>

            <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-6 sm:p-8">
              <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[#001529]">
                <KeyOutlined className="text-amber-600" />
                Ключ LLM-провайдера (опционально)
              </h3>
              <p className="mb-4 text-sm leading-relaxed text-slate-700">
                Для более живых описаний маршрутов и справок о местах укажите API-ключ
                OpenAI-compatible провайдера (по умолчанию —{" "}
                <a
                  href="https://proxyapi.ru"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-sky-700 underline decoration-sky-300 underline-offset-2 hover:text-sky-900"
                  onClick={() => reachGoal(METRIKA_GOALS.PROXYAPI_LINK_CLICK)}
                >
                  ProxyAPI
                </a>
                ). Модель помогает собрать варианты A/B/C по пулу мест в городе.
              </p>
              <div className="mb-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-amber-100 bg-white/70 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Без ключа
                  </p>
                  <ul className="m-0 list-none space-y-2 p-0 text-sm text-slate-700">
                    <li>Алгоритм без LLM</li>
                    <li>Пул мест из Wikipedia</li>
                    <li>До 30 сборок в сутки</li>
                  </ul>
                </div>
                <div className="rounded-xl border border-amber-200 bg-white p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
                    С LLM-ключом
                  </p>
                  <ul className="m-0 list-none space-y-2 p-0 text-sm text-slate-700">
                    <li>Живее формулировки маршрутов и справок</li>
                    <li>Расширенный справочник, если город подготовлен</li>
                    <li>Обычно больше мест в пуле</li>
                  </ul>
                </div>
              </div>
              <ul className="m-0 list-none space-y-3 p-0 text-sm text-slate-700">
                <li className="flex gap-2">
                  <span className="text-amber-600">•</span>
                  <span>
                    <strong>Где взять:</strong> регистрация на proxyapi.ru или другом провайдере,
                    ключ в личном кабинете; небольшого баланса обычно хватает на несколько пересборов.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-amber-600">•</span>
                  <span>
                    <strong>Куда вставить:</strong> «Настройки» после входа. Ключ хранится в
                    зашифрованном виде.
                  </span>
                </li>
              </ul>
              <p className="mt-4 flex items-start gap-2 text-xs text-slate-600">
                <SafetyOutlined className="mt-0.5 shrink-0 text-slate-500" />
                Ключ не показывается целиком повторно — как пароль. Его можно заменить или удалить.
              </p>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-[#001529] px-4 py-10 text-slate-300 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <p className="mb-1 flex items-center gap-2 text-base font-semibold text-white">
              <CompassOutlined className="text-sky-400" />
              {APP_NAME}
            </p>
            <p className="m-0 text-sm text-slate-400">
              {APP_TAGLINE} — выберите свой вариант и идите с картой в руках.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to="/login" onClick={() => reachGoal(METRIKA_GOALS.CTA_LOGIN_CLICK)}>
              <Button ghost>Войти</Button>
            </Link>
            <Link to="/register" onClick={() => reachGoal(METRIKA_GOALS.CTA_REGISTER_CLICK)}>
              <Button type="primary">Регистрация</Button>
            </Link>
          </div>
        </div>
        <div className="mx-auto mt-8 flex max-w-6xl flex-wrap gap-x-4 gap-y-2 border-t border-white/10 pt-6 text-sm text-slate-400">
          <HowRoutesWorkDrawer
            link
            className="!text-slate-400 hover:!text-white"
          />
          <Link to="/terms" className="text-slate-400 no-underline hover:text-white">
            Пользовательское соглашение
          </Link>
          <Link to="/privacy" className="text-slate-400 no-underline hover:text-white">
            Политика конфиденциальности
          </Link>
          <Link to="/privacy#cookies" className="text-slate-400 no-underline hover:text-white">
            Cookie и Метрика
          </Link>
        </div>
      </footer>
    </div>
  );
}
