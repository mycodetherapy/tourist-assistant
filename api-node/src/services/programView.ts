import { makeItemKey, makeRouteStopKey } from "../lib/itemKey.js";
import type { ItineraryVersion } from "../repos/trips.js";
import { listItemFeedback } from "../repos/trips.js";
import {
  collectRouteStopPoiIds,
  parseNumberedSection,
  parseRoutesSection,
} from "./parseProgram.js";

export type CityFactStatus =
  | "pending"
  | "ready"
  | "failed"
  | "skipped"
  | "idle";

export interface ProgramItemView {
  index: number;
  item_key: string;
  text: string;
  vote: 1 | -1 | null;
  poi_id?: string | null;
}

export interface ProgramSectionView {
  intro: string;
  items: ProgramItemView[];
}

export interface ProgramView {
  version: number;
  version_id: number;
  scope: string;
  approved: boolean;
  program: Record<string, unknown>;
  sections: {
    routes: ProgramSectionView;
    route_stops: ProgramSectionView;
    lifehacks: ProgramSectionView;
  };
  data_warnings: string[];
  city_fact_status: CityFactStatus;
}

function resolveCityFactStatus(program: Record<string, unknown>): CityFactStatus {
  const raw = program.city_fact_status;
  if (raw === "pending" || raw === "ready" || raw === "failed" || raw === "skipped") {
    return raw;
  }
  if (String(program.lifehacks ?? "").trim()) return "ready";
  return "idle";
}

function normalizeProgram(data: Record<string, unknown>): Record<string, unknown> {
  const out = { ...data };
  if (!out.lifehacks) out.lifehacks = "";
  return out;
}

export async function buildProgramView(
  tripId: number,
  latest: ItineraryVersion,
): Promise<ProgramView> {
  const programData = normalizeProgram({ ...latest.program });
  const votesByKey = await listItemFeedback(tripId);

  const routesText = String(programData.routes_text ?? "");
  const routesParsed = routesText
    ? parseRoutesSection(routesText)
    : { intro: "", items: [] as string[] };
  const routesItems: ProgramItemView[] = routesParsed.items.map((text, index) => {
    const key = makeItemKey("routes", text);
    const vote = votesByKey[key];
    return {
      index,
      item_key: key,
      text,
      vote: vote === 1 || vote === -1 ? vote : null,
    };
  });

  const poiLabels = collectRouteStopPoiIds(programData);
  const poiIds = Object.keys(poiLabels);
  const routeStopItems: ProgramItemView[] = poiIds.map((poiId, index) => {
    const key = makeRouteStopKey(poiId);
    const vote = votesByKey[key];
    return {
      index,
      item_key: key,
      text: `${poiLabels[poiId]} [${poiId}]`,
      vote: vote === 1 || vote === -1 ? vote : null,
      poi_id: poiId,
    };
  });

  const lifehacksText = String(programData.lifehacks ?? "");
  const lifeParsed = parseNumberedSection(lifehacksText);
  const lifeItems: ProgramItemView[] = lifeParsed.items.map((text, index) => {
    const key = makeItemKey("lifehacks", text);
    const vote = votesByKey[key];
    return {
      index,
      item_key: key,
      text,
      vote: vote === 1 || vote === -1 ? vote : null,
    };
  });

  const rawWarnings = programData.data_warnings;
  const dataWarnings = Array.isArray(rawWarnings)
    ? rawWarnings.map((w) => String(w).trim()).filter(Boolean)
    : [];

  return {
    version: latest.version,
    version_id: latest.id,
    scope: latest.scope,
    approved: latest.approved,
    program: {
      routes: programData.routes ?? null,
      routes_text: programData.routes_text ?? "",
      lifehacks: programData.lifehacks ?? "",
    },
    sections: {
      routes: { intro: routesParsed.intro, items: routesItems },
      route_stops: { intro: "", items: routeStopItems },
      lifehacks: { intro: lifeParsed.intro, items: lifeItems },
    },
    data_warnings: dataWarnings,
    city_fact_status: resolveCityFactStatus(programData),
  };
}
