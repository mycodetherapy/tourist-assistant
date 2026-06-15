import type { MapPoint } from "../components/RouteAnchorMapPicker";

export interface ParsedCoordinate {
  lat: number;
  lon: number;
  label: string;
}

function isValidLatLon(lat: number, lon: number): boolean {
  return (
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    lat >= -90 &&
    lat <= 90 &&
    lon >= -180 &&
    lon <= 180
  );
}

/** «56.85, 35.88» или «56.85 35.88» → координаты. */
export function parseCoordinateQuery(raw: string): ParsedCoordinate | null {
  const query = raw.trim();
  if (!query) {
    return null;
  }

  const commaMatch = query.match(/^(-?\d+(?:[.,]\d+)?)\s*[,;]\s*(-?\d+(?:[.,]\d+)?)$/);
  if (commaMatch) {
    const lat = Number.parseFloat(commaMatch[1].replace(",", "."));
    const lon = Number.parseFloat(commaMatch[2].replace(",", "."));
    if (isValidLatLon(lat, lon)) {
      return { lat, lon, label: query };
    }
  }

  const spaceMatch = query.match(/^(-?\d+(?:[.,]\d+)?)\s+(-?\d+(?:[.,]\d+)?)$/);
  if (spaceMatch) {
    const lat = Number.parseFloat(spaceMatch[1].replace(",", "."));
    const lon = Number.parseFloat(spaceMatch[2].replace(",", "."));
    if (isValidLatLon(lat, lon)) {
      return { lat, lon, label: query };
    }
  }

  return null;
}

export function toMapPoint(parsed: ParsedCoordinate): MapPoint {
  return { lat: parsed.lat, lon: parsed.lon };
}
