import {
  CompassOutlined,
  KeyOutlined,
  LoginOutlined,
  SafetyOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import { Button } from "antd";
import { Link } from "react-router-dom";

const STEPS = [
  {
    title: "Расскажите о поездке",
    text: "Город, даты, бюджет и ваши интересы — как если бы вы писали другу, куда хотите поехать.",
  },
  {
    title: "Ассистент собирает план",
    text: "Он ищет актуальную информацию в интернете и составляет маршрут: что посмотреть, где поесть, как добраться.",
  },
  {
    title: "Вы правите и утверждаете",
    text: "Программу можно доработать: попросить больше музеев, убрать лишнее или пересобрать отдельный день.",
  },
  {
    title: "Берёте с собой",
    text: "Готовый план с картой, ссылками и подсказками — открываете на телефоне в дороге.",
  },
] as const;

const FEATURES = [
  {
    title: "Маршрут по дням",
    text: "Утро, день и вечер — без спешки и «галочек ради галочек».",
  },
  {
    title: "Билеты и отели",
    text: "Подсказки, где искать жильё и транспорт, с ориентирами по цене.",
  },
  {
    title: "Карта и адреса",
    text: "Места на карте, чтобы не теряться в незнакомом городе.",
  },
  {
    title: "Ваш стиль отдыха",
    text: "Спокойная прогулка, музеи, еда или актив — ассистент подстраивается под вас.",
  },
] as const;

export function LandingPage() {
  return (
    <div className="landing min-h-dvh bg-[#f8fafc] text-slate-800">
      <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-2 text-lg font-semibold text-[#001529] no-underline">
            <CompassOutlined className="text-xl text-sky-600" />
            <span>Tourist Assistant</span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link to="/login">
              <Button icon={<LoginOutlined />}>Войти</Button>
            </Link>
            <Link to="/register">
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
          <p className="mb-3 text-sm font-medium uppercase tracking-wider text-sky-700">Планировщик путешествий</p>
          <h1 className="mb-5 max-w-3xl text-3xl font-bold leading-tight text-[#001529] sm:text-4xl lg:text-5xl">
            Персональный маршрут поездки — без бесконечных вкладок и таблиц
          </h1>
          <p className="mb-8 max-w-2xl text-base leading-relaxed text-slate-600 sm:text-lg">
            Tourist Assistant помогает спланировать поездку: описываете пожелания — получаете понятную программу с
            местами, картой и практичными советами. Для самостоятельных путешественников, которые хотят готовый план,
            а не сухой список достопримечательностей.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/register">
              <Button type="primary" size="large" icon={<UserAddOutlined />}>
                Создать аккаунт
              </Button>
            </Link>
            <Link to="/login">
              <Button size="large" icon={<LoginOutlined />}>
                Уже есть аккаунт
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <h2 className="mb-3 text-2xl font-bold text-[#001529] sm:text-3xl">Что вы получите</h2>
          <p className="mb-10 max-w-2xl text-slate-600">
            Не замена гиду и не бронирование «под ключ» — умный помощник, который экономит часы на подготовку.
          </p>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((item) => (
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
          <p className="mb-10 max-w-2xl text-slate-600">
            Без сложных настроек: несколько шагов от идеи до готового плана на экране телефона.
          </p>
          <ol className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
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
                Аккаунт в сервисе
              </h3>
              <ul className="m-0 list-none space-y-3 p-0 text-slate-600">
                <li className="flex gap-2">
                  <span className="text-sky-600">•</span>
                  <span>Регистрация по email и паролю или вход через Google.</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-sky-600">•</span>
                  <span>Ваши поездки хранятся отдельно — только у вас в личном кабинете.</span>
                </li>
              </ul>
              <div className="mt-6">
                <Link to="/register">
                  <Button type="primary">Зарегистрироваться</Button>
                </Link>
              </div>
            </div>

            <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-6 sm:p-8">
              <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-[#001529]">
                <KeyOutlined className="text-amber-600" />
                Ключ OpenRouter
              </h3>
              <p className="mb-4 text-sm leading-relaxed text-slate-700">
                Для работы ассистента нужен API-ключ от{" "}
                <a
                  href="https://openrouter.ai/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-sky-700 underline decoration-sky-300 underline-offset-2 hover:text-sky-900"
                >
                  OpenRouter
                </a>
                . Это сервис, через который запускается «мозг» планировщика — языковая модель, которая читает ваши
                пожелания и собирает маршрут.
              </p>
              <ul className="m-0 list-none space-y-3 p-0 text-sm text-slate-700">
                <li className="flex gap-2">
                  <span className="text-amber-600">•</span>
                  <span>
                    <strong>Зачем:</strong> без ключа ассистент не сможет составить программу. Вы платите OpenRouter
                    напрямую за использование модели — мы не продаём «пакеты запросов».
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-amber-600">•</span>
                  <span>
                    <strong>Где взять:</strong> зарегистрируйтесь на openrouter.ai, пополните баланс (обычно хватает
                    небольшой суммы на одну-две поездки) и создайте ключ в разделе Keys.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-amber-600">•</span>
                  <span>
                    <strong>Куда вставить:</strong> после входа откройте «Настройки» в шапке сайта и сохраните ключ
                    там. Он хранится в зашифрованном виде и используется только для ваших поездок.
                  </span>
                </li>
              </ul>
              <p className="mt-4 flex items-start gap-2 text-xs text-slate-600">
                <SafetyOutlined className="mt-0.5 shrink-0 text-slate-500" />
                Ключ не показывается повторно целиком — как пароль. Его можно заменить или удалить в любой момент.
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
              Tourist Assistant
            </p>
            <p className="m-0 text-sm text-slate-400">Планируйте поездку спокойно — мы поможем собрать маршрут.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to="/login">
              <Button ghost>Войти</Button>
            </Link>
            <Link to="/register">
              <Button type="primary">Регистрация</Button>
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
