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
  return out.join("\n");
}

function expandInlineDotItems(line: string): string[] {
  const parts = line.split(" · ").map((p) => p.trim()).filter(Boolean);
  if (parts.length <= 1) {
    return [line];
  }
  return [parts[0], "", ...parts.slice(1).map((p) => `- ${p}`)];
}
