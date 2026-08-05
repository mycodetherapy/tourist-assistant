/** Markdown section parsing (subset of program/parse_items.py). */

export interface ParsedSection {
  intro: string;
  items: string[];
}

interface RouteCaseRaw {
  case_id?: string;
  title?: string;
  summary?: string;
  maps_route_url?: string;
  preserved?: boolean;
  stops?: Array<{
    kind?: string;
    poi_id?: string;
    narrative?: string;
  }>;
}

const NUMBERED_ITEM = /^\d+\.\s+/;
const CONTINUATION = /^(\s{2,}|·\s)/;
const ROUTE_PARENS = /\s*\([^)]*\)/g;
const KM_SNIPPET = /~?\s*\d+(?:[.,]\d+)?\s*(?:–\s*\d+(?:[.,]\d+)?)?\s*км\.?/gi;

function isContinuation(line: string): boolean {
  return CONTINUATION.test(line);
}

export function parseNumberedSection(text: string): ParsedSection {
  const lines = text.split("\n");
  const introLines: string[] = [];
  const items: string[] = [];
  let current: string[] = [];

  const flush = () => {
    if (current.length) {
      items.push(current.join("\n").trim());
      current = [];
    }
  };

  for (const line of lines) {
    if (NUMBERED_ITEM.test(line)) {
      flush();
      current = [line];
    } else if (current.length && isContinuation(line)) {
      current.push(line);
    } else if (current.length) {
      current.push(line);
    } else {
      introLines.push(line);
    }
  }
  flush();

  if (!items.length && text.trim()) {
    return { intro: text.trim(), items: [] };
  }
  return { intro: introLines.join("\n").trim(), items };
}

function publicRouteTitle(title: string): string {
  return title.replace(ROUTE_PARENS, "").trim();
}

function publicRouteSummary(summary: string): string {
  let text = summary.replace(ROUTE_PARENS, "");
  text = text.replace(KM_SNIPPET, "");
  text = text.replace(/\s{2,}/g, " ");
  text = text.replace(/,\s*,/g, ",");
  return text.trim().replace(/^[,:\s—-]+|[,:\s—-]+$/g, "");
}

/** Как program/parse_items._format_route_item_block — ключи голосов совпадают с Python worker. */
export function formatRouteItemBlock(caseData: RouteCaseRaw): string {
  const caseId = String(caseData.case_id ?? "?");
  const title = publicRouteTitle(String(caseData.title ?? ""));
  const url = String(caseData.maps_route_url ?? "").trim();
  const leisure = (caseData.stops ?? []).filter(
    (stop) => stop.kind === "leisure",
  );
  const meta =
    leisure.length > 0
      ? `${leisure.length} остановок`
      : publicRouteSummary(String(caseData.summary ?? "").trim());
  let block = `**Вариант ${caseId}: ${title}** — ${meta}`;
  if (url) {
    block += `\n\n[Открыть маршрут в Яндекс.Картах](${url})`;
  }
  for (const stop of leisure) {
    const narrative = String(stop.narrative ?? "").trim();
    if (narrative) {
      block += `\n- ${narrative}`;
    }
  }
  return block.trim();
}

/** Structured program.routes.cases — приоритет над routes_text (как parse_program_sections). */
export function parseRoutesFromStructured(
  program: Record<string, unknown>,
): ParsedSection | null {
  const raw = program.routes;
  if (!raw || typeof raw !== "object") return null;
  const cases = (raw as { cases?: RouteCaseRaw[] }).cases;
  if (!Array.isArray(cases) || cases.length === 0) return null;
  const routesText = String(program.routes_text ?? "");
  const intro = routesText.split("##")[0]?.trim() ?? "";
  const items = cases
    .filter((caseData) => caseData && typeof caseData === "object")
    .map((caseData) => formatRouteItemBlock(caseData));
  return { intro, items };
}

export function parseRoutesSection(routesText: string): ParsedSection {
  const lines = routesText.split("\n");
  const items: string[] = [];
  let current: string[] = [];
  const introLines: string[] = [];
  const ROUTE_HEADER = /^##\s+Вариант\s+([^:\n]+):/i;

  const flush = () => {
    if (current.length) {
      items.push(current.join("\n").trim());
      current = [];
    }
  };

  for (const line of lines) {
    if (ROUTE_HEADER.test(line)) {
      flush();
      current = [line];
    } else if (current.length) {
      current.push(line);
    } else {
      introLines.push(line);
    }
  }
  flush();

  if (!items.length && routesText.trim()) {
    return parseNumberedSection(routesText);
  }
  return { intro: introLines.join("\n").trim(), items };
}

/** Маршруты для голосов UI и worker: structured → fallback routes_text. */
export function parseProgramRoutes(
  program: Record<string, unknown>,
): ParsedSection {
  const structured = parseRoutesFromStructured(program);
  if (structured && structured.items.length > 0) {
    return structured;
  }
  const routesText = String(program.routes_text ?? "");
  if (routesText.trim()) {
    return parseRoutesSection(routesText);
  }
  return { intro: "", items: [] };
}

export function collectRouteStopPoiIds(
  program: Record<string, unknown>,
): Record<string, string> {
  const raw = program.routes;
  if (!raw || typeof raw !== "object") return {};
  const routes = raw as {
    cases?: Array<{
      stops?: Array<{
        kind?: string;
        poi_id?: string;
        narrative?: string;
      }>;
    }>;
  };
  const out: Record<string, string> = {};
  for (const c of routes.cases ?? []) {
    for (const stop of c.stops ?? []) {
      if (stop.kind !== "leisure" || !stop.poi_id) continue;
      const label = (stop.narrative ?? "").trim() || stop.poi_id;
      if (!out[stop.poi_id]) out[stop.poi_id] = label;
    }
  }
  return out;
}
