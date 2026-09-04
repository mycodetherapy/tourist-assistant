/** Тексты про бесплатный vs LLM режим и источники пула мест. */

export type PoiPoolProvider = "osm" | "wikidata" | "demo" | "mixed" | "unknown";

export function parsePoolProvider(raw: string | null | undefined): PoiPoolProvider {
  const text = (raw || "").toLowerCase();
  if (/\(osm\)/.test(text) || text.includes("city pack") || text.includes("справочник")) {
    return "osm";
  }
  if (/\(wikidata\)/.test(text) || text.includes("wikipedia")) {
    return "wikidata";
  }
  if (/\(demo\)/.test(text)) {
    return "demo";
  }
  if (/\(mixed\)/.test(text)) {
    return "mixed";
  }
  return "unknown";
}

export function parsePoolCount(raw: string | null | undefined): number | null {
  const m = (raw || "").match(/Пул:\s*(\d+)/i);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
}

export function providerLabel(provider: PoiPoolProvider): string {
  switch (provider) {
    case "osm":
      return "справочник города";
    case "wikidata":
      return "Wikipedia";
    case "demo":
      return "демо-точки";
    case "mixed":
      return "смешанный пул";
    default:
      return "открытые данные";
  }
}

export function providerTooltip(provider: PoiPoolProvider): string {
  switch (provider) {
    case "osm":
      return "Места из подготовленного справочника города (OSM). Обычно доступен в режиме с LLM, если город загружен на сервер.";
    case "wikidata":
      return "Места из Wikipedia/Wikidata. Так работает бесплатный режим и города без готового справочника.";
    case "demo":
      return "Демо-точки: внешних данных по городу не хватило.";
    case "mixed":
      return "Часть мест из справочника города, часть из Wikipedia.";
    default:
      return "Число — сколько кандидатов было у сборщика, не длина маршрута.";
  }
}

export const FREE_VS_LLM = {
  freeTitle: "Бесплатно (алгоритм)",
  llmTitle: "С LLM-ключом",
  freeBullets: [
    "Маршруты собирает алгоритм, без LLM",
    "Пул мест — из Wikipedia (обычно до ~50 кандидатов)",
    "До 30 сборок в сутки",
  ],
  llmBullets: [
    "LLM помогает формулировать маршруты и справки",
    "Если город подготовлен на сервере — расширенный справочник (больше мест)",
    "Справки о местах и городе через LLM",
  ],
  shortCompare:
    "Без ключа — алгоритм и Wikipedia. С ключом LLM — живее описания и, если город у нас подготовлен, более полный справочник города.",
  guestHint:
    "Пробный режим = бесплатная сборка (алгоритм + Wikipedia). LLM и расширенный справочник города — после аккаунта и ключа в настройках.",
  rebuildRoutesHint:
    "Пересбор строит новые A/B/C по тому же пулу. 📌 сохраняет вариант при пересборе; 👍/👎 мягко влияют на новые маршруты. Дизлайк остановок убирает их из следующих вариантов. Глубокий пересбор заново обновляет список мест.",
  likesHint:
    "📌 — сохранить маршрут при пересборе. 👍/👎 у варианта и остановок — мягкая подсказка для новой сборки (путь не копируется).",
  cityPackHint:
    "«Город подготовлен» значит, что для него на сервере есть справочник мест. В бесплатном режиме он не используется — только с LLM.",
} as const;

export const HOW_ROUTES_WORK_SECTIONS = [
  {
    title: "Бесплатный режим",
    body: "Маршруты строит алгоритм. Места берутся из Wikipedia/Wikidata (базовый пул). LLM не вызывается.",
  },
  {
    title: "Режим с LLM",
    body: "Нужен API-ключ в настройках. Модель помогает описать прогулку и справки. Если город подготовлен на сервере, подключается расширенный справочник мест — обычно пул заметно больше.",
  },
  {
    title: "Сохранение и оценки",
    body: "📌 сохраняет понравившийся A/B/C — он останется, пока остальные пересоберутся. 👍/👎 у маршрута и остановок мягко влияют на следующую сборку, но не закрепляют путь.",
  },
  {
    title: "Пересбор",
    body: "«Пересобрать маршруты» — новые A/B/C из текущего пула с учётом 📌 и оценок. Без оценок алгоритм может выдать похожие варианты. «Глубокий пересбор» — заново ищет места, затем строит маршруты.",
  },
  {
    title: "Карта",
    body: "Линия по улицам появляется, когда для города есть пеший граф на сервере. Иначе остаётся виджет Яндекс.Карт. Готовой картой можно пользоваться в любом режиме; подготовить новый город — в настройках, в режиме со своим API-ключом.",
  },
] as const;
