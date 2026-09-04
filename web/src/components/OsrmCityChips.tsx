import { CheckCircleFilled } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Button, Grid } from "antd";
import { useMemo, useState } from "react";
import { fetchOsrmReadyCities, type OsrmReadyCity } from "../api/cities";
import {
  findExactOsrmCity,
  rememberRecentOsrmSlug,
  readRecentOsrmSlugs,
  sortOsrmCities,
  visibleOsrmCities,
} from "../utils/osrmCityChips";

const { useBreakpoint } = Grid;

interface OsrmCityChipsProps {
  onSelect: (displayName: string) => void;
  selectedCity?: string;
}

export function OsrmCityMatchBadge({ city }: { city: string }) {
  const query = useQuery({
    queryKey: ["cities", "osrm-ready"],
    queryFn: fetchOsrmReadyCities,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const match = findExactOsrmCity(query.data ?? [], city);
  if (!match) {
    return null;
  }
  return (
    <span
      className="text-sky-600"
      title={`«${match.display_name}»: линия маршрута по улицам`}
    >
      <CheckCircleFilled aria-label="Есть линия маршрута по улицам" />
    </span>
  );
}

export function OsrmCityChips({ onSelect, selectedCity = "" }: OsrmCityChipsProps) {
  const screens = useBreakpoint();
  const collapsedLimit = screens.md ? 10 : 6;
  const [expanded, setExpanded] = useState(false);
  const [recentSlugs, setRecentSlugs] = useState<string[]>(() => readRecentOsrmSlugs());

  const query = useQuery({
    queryKey: ["cities", "osrm-ready"],
    queryFn: fetchOsrmReadyCities,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const cities = query.data;
  const sorted = useMemo(
    () => sortOsrmCities(cities ?? [], recentSlugs, selectedCity),
    [cities, recentSlugs, selectedCity],
  );
  const { shown, hidden, filtering } = useMemo(
    () => visibleOsrmCities(sorted, selectedCity, expanded, collapsedLimit),
    [sorted, selectedCity, expanded, collapsedLimit],
  );
  const exact = findExactOsrmCity(cities ?? [], selectedCity);

  const pickCity = (city: OsrmReadyCity) => {
    rememberRecentOsrmSlug(city.slug);
    setRecentSlugs(readRecentOsrmSlugs());
    onSelect(city.display_name);
  };

  if (query.isLoading) {
    return (
      <p className="mb-4 text-xs text-slate-400">Загрузка городов с картой по улицам…</p>
    );
  }

  if (query.isError) {
    return (
      <p className="mb-4 text-xs text-amber-700">
        Не удалось загрузить список городов с линией по улицам. Можно ввести город вручную.
      </p>
    );
  }

  if (!cities?.length) {
    return (
      <p className="mb-4 text-xs text-slate-500">
        На этом сервере пока нет готовых OSRM-графов — введите город вручную.
      </p>
    );
  }

  const selected = selectedCity.trim().toLowerCase();

  let hint: string;
  if (exact) {
    hint = `«${exact.display_name}» — будет линия маршрута по улицам.`;
  } else if (filtering && shown.length === 0) {
    hint =
      "Города с картой по улицам по этому запросу нет. Можно оставить как есть — соберём маршрут, на карте будет виджет Яндекса.";
  } else if (filtering) {
    hint = "Города с линией по улицам по запросу — нажмите, чтобы подставить.";
  } else {
    hint =
      "Города с линией маршрута по улицам из OpenStreetMap — нажмите, чтобы подставить. В любом другом городе маршруты тоже соберутся (виджет Яндекса).";
  }

  return (
    <div className="mb-4">
      <p className="mb-2 text-xs leading-relaxed text-slate-500">{hint}</p>
      {shown.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {shown.map((city) => {
            const active = selected === city.display_name.trim().toLowerCase();
            return (
              <button
                key={city.slug}
                type="button"
                aria-pressed={active}
                className={`rounded-full border px-3 py-1 text-sm transition ${
                  active
                    ? "border-sky-500 bg-sky-50 text-sky-900"
                    : "border-slate-200 bg-white text-slate-700 hover:border-sky-300 hover:bg-sky-50/60"
                }`}
                onClick={() => pickCity(city)}
              >
                {city.display_name}
              </button>
            );
          })}
        </div>
      ) : null}
      {hidden > 0 ? (
        <Button
          type="link"
          size="small"
          className="!mt-1 !h-auto !px-0"
          onClick={() => setExpanded(true)}
        >
          Ещё {hidden} {hiddenCityWord(hidden)}
        </Button>
      ) : null}
      {expanded && !filtering && sorted.length > collapsedLimit ? (
        <Button
          type="link"
          size="small"
          className="!mt-1 !h-auto !px-0"
          onClick={() => setExpanded(false)}
        >
          Свернуть
        </Button>
      ) : null}
    </div>
  );
}

function hiddenCityWord(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) {
    return "город";
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return "города";
  }
  return "городов";
}
