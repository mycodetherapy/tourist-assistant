import type { LeisureTag } from "../api/types";

export const LEISURE_LABELS: Record<LeisureTag, string> = {
  landmarks: "Достопримечательности",
  museums: "Музеи",
  exhibitions: "Выставки",
  galleries: "Галереи",
  philharmonic: "Филармонии",
  theaters: "Театры",
  parks: "Парки",
};

export const OPTIONAL_LEISURE_TAGS: LeisureTag[] = [
  "museums",
  "exhibitions",
  "galleries",
  "philharmonic",
  "theaters",
  "parks",
];
