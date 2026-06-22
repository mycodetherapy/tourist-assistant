/** Markdown section parsing (subset of program/parse_items.py). */

export interface ParsedSection {
  intro: string;
  items: string[];
}

const NUMBERED_ITEM = /^\d+\.\s+/;
const CONTINUATION = /^(\s{2,}|·\s)/;

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

export function parseRoutesSection(routesText: string): ParsedSection {
  const lines = routesText.split("\n");
  const items: string[] = [];
  let current: string[] = [];
  const ROUTE_HEADER = /^##\s+Вариант\s+([ABC]):/i;

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
    }
  }
  flush();

  if (!items.length && routesText.trim()) {
    return parseNumberedSection(routesText);
  }
  return { intro: "", items };
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
