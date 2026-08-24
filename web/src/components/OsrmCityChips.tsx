import { useQuery } from "@tanstack/react-query";
import { fetchOsrmReadyCities, type OsrmReadyCity } from "../api/cities";

interface OsrmCityChipsProps {
  onSelect: (displayName: string) => void;
  selectedCity?: string;
}

export function OsrmCityChips({ onSelect, selectedCity = "" }: OsrmCityChipsProps) {
  const query = useQuery({
    queryKey: ["cities", "osrm-ready"],
    queryFn: fetchOsrmReadyCities,
    staleTime: 5 * 60_000,
    retry: 1,
  });

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

  const cities: OsrmReadyCity[] = query.data ?? [];
  if (cities.length === 0) {
    return (
      <p className="mb-4 text-xs text-slate-500">
        На этом сервере пока нет готовых OSRM-графов — введите город вручную.
      </p>
    );
  }

  const selected = selectedCity.trim().toLowerCase();

  return (
    <div className="mb-4">
      <p className="mb-2 text-xs leading-relaxed text-slate-500">
        Города с линией маршрута по улицам из OpenStreetMap — нажмите, чтобы подставить. В любом другом городе
        маршруты тоже соберутся (будет использован виджет Яндекса).
      </p>
      <div className="flex flex-wrap gap-2">
        {cities.map((city) => {
          const active = selected === city.display_name.trim().toLowerCase();
          return (
            <button
              key={city.slug}
              type="button"
              className={`rounded-full border px-3 py-1 text-sm transition ${
                active
                  ? "border-sky-500 bg-sky-50 text-sky-900"
                  : "border-slate-200 bg-white text-slate-700 hover:border-sky-300 hover:bg-sky-50/60"
              }`}
              onClick={() => onSelect(city.display_name)}
            >
              {city.display_name}
            </button>
          );
        })}
      </div>
    </div>
  );
}
