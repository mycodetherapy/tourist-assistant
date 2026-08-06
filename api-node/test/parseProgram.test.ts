import { describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import {
  formatRouteItemBlock,
  parseProgramRoutes,
  parseRoutesSection,
} from "../src/services/parseProgram.js";
import { makeItemKey } from "../src/lib/itemKey.js";

function pyMakeItemKey(section: string, text: string): string {
  const normalized = text.trim().toLowerCase().replace(/\s+/g, " ");
  const payload = `${section}:${normalized}`;
  return createHash("sha256").update(payload, "utf8").digest("hex").slice(0, 16);
}

describe("parseProgramRoutes", () => {
  it("uses structured routes.cases for vote keys (Python parity)", () => {
    const program = {
      routes_text:
        "## Вариант A: Legacy title\n\nold markdown that differs",
      routes: {
        cases: [
          {
            case_id: "A",
            title: "Лёгкая прогулка (~3 км)",
            summary: "3 остановки",
            maps_route_url: "https://yandex.ru/maps/?rtext=1",
            stops: [
              { order: 1, kind: "leisure", poi_id: "l1", narrative: "Музей" },
              { order: 2, kind: "leisure", poi_id: "l2", narrative: "Площадь" },
            ],
          },
        ],
      },
    };
    const parsed = parseProgramRoutes(program);
    expect(parsed.items).toHaveLength(1);
    expect(parsed.items[0]).toContain("**Вариант A: Лёгкая прогулка**");
    expect(parsed.items[0]).toContain("2 остановок");
    expect(makeItemKey("routes", parsed.items[0]!)).toBe(
      pyMakeItemKey("routes", parsed.items[0]!),
    );
    expect(makeItemKey("routes", parsed.items[0]!)).not.toBe(
      makeItemKey("routes", "## Вариант A: Legacy title\n\nold markdown that differs"),
    );
  });

  it("parses N-A route headers from routes_text fallback", () => {
    const text = [
      "## Вариант A: Liked",
      "- stop",
      "",
      "## Вариант N-A: New",
      "- other",
    ].join("\n");
    const parsed = parseRoutesSection(text);
    expect(parsed.items).toHaveLength(2);
    expect(parsed.items[1]).toContain("N-A");
  });

  it("formatRouteItemBlock matches expected shape", () => {
    const block = formatRouteItemBlock({
      case_id: "N-B",
      title: "Средний маршрут",
      summary: "fallback",
      maps_route_url: "https://maps.example/r",
      stops: [{ kind: "leisure", narrative: "Парк" }],
    });
    expect(block).toBe(
      "**Вариант N-B: Средний маршрут** — 1 остановок\n\n[Открыть маршрут в Яндекс.Картах](https://maps.example/r)\n- Парк",
    );
  });
});
