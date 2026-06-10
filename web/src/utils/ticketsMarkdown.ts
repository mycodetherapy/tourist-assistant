/** Нормализация markdown билетов для ReactMarkdown. */
export function normalizeTicketsMarkdown(text: string): string {
  if (!text.trim()) {
    return text;
  }
  const lineRe =
    /^(?:(\*\*[^*]+\*\*|(?:Самолёт|Поезд|Автобус)):\s*)?(-\s*)?(.+):\s+(https?:\/\/\S+)\s*$/;
  const out: string[] = [];
  for (const line of text.split("\n")) {
    const stripped = line.trim();
    if (stripped.startsWith("·")) {
      out.push(`- ${stripped.slice(1).trim()}`);
      continue;
    }
    if (line.includes(" · ") && !stripped.startsWith("-")) {
      out.push(...expandInlineDotItems(line));
      continue;
    }
    if (line.includes("](http") && !line.includes(": https://")) {
      out.push(line);
      continue;
    }
    const m = stripped.match(lineRe);
    if (!m) {
      out.push(line);
      continue;
    }
    const [, prefix = "", bullet = "", label, url] = m;
    out.push(`${prefix}${bullet}[${label.trim()}](${url})`);
  }
  return enrichAviasalesLinkLabels(out.join("\n"));
}

function expandInlineDotItems(line: string): string[] {
  const parts = line.split(" · ").map((p) => p.trim()).filter(Boolean);
  if (parts.length <= 1) {
    return [line];
  }
  return [parts[0], "", ...parts.slice(1).map((p) => `- ${p}`)];
}

function routePaxFromIntro(text: string): string | null {
  const routeM = text.match(/Маршрут:\s*(.+?)\s*→\s*(.+?)(?:,\s*даты:|$)/m);
  if (!routeM) {
    return null;
  }
  const origin = routeM[1].trim();
  const dest = routeM[2].trim();
  const paxM = text.match(/Пассажиры в ссылках:\s*(.+)$/m);
  let paxSuffix = "";
  if (paxM) {
    let pax = paxM[1].trim();
    if (pax.endsWith("..")) {
      pax = pax.slice(0, -1);
    }
    if (pax && pax !== "1 взр.") {
      paxSuffix = ` (${pax})`;
    }
  }
  return `${origin} → ${dest}${paxSuffix}`;
}

function routePaxFromTransportLinks(text: string): string | null {
  for (const m of text.matchAll(/\[([^\]]+)\]\(/g)) {
    const label = m[1].trim();
    const low = label.toLowerCase();
    if (
      !label.includes("→") ||
      low.startsWith("все рейсы на aviasales") ||
      low.startsWith("aviasales")
    ) {
      continue;
    }
    const colon = label.indexOf(":");
    if (colon >= 0) {
      const tail = label.slice(colon + 1).trim();
      if (tail.includes("→")) {
        return tail;
      }
    }
  }
  return null;
}

function resolveRoutePaxLabel(text: string): string | null {
  const fromIntro = routePaxFromIntro(text);
  if (fromIntro) {
    return fromIntro;
  }
  return routePaxFromTransportLinks(text);
}

function enrichAviasalesLinkLabels(text: string): string {
  const routePax = resolveRoutePaxLabel(text);
  if (!routePax) {
    return text;
  }
  const fullLabel = `Все рейсы на Aviasales: ${routePax}`;
  return text.replace(
    /\[([^\]]*)\]\((https?:\/\/[^)]*aviasales[^)]*)\)/gi,
    (full, label, url) => {
      const trimmed = label.trim();
      if (trimmed.includes("→")) {
        return full;
      }
      if (
        trimmed === "Все рейсы на Aviasales" ||
        trimmed === "Aviasales" ||
        trimmed.startsWith("Aviasales:")
      ) {
        return `[${fullLabel}](${url})`;
      }
      return full;
    },
  );
}
