export class GeolocationError extends Error {
  readonly code: "unavailable" | "insecure" | "denied" | "timeout" | "position" | "unknown";

  constructor(message: string, code: GeolocationError["code"] = "unknown") {
    super(message);
    this.name = "GeolocationError";
    this.code = code;
  }
}

export function geolocationUnavailableMessage(): string | null {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return "Геолокация не поддерживается в этом браузере";
  }
  if (typeof window !== "undefined" && !window.isSecureContext) {
    return "Откройте сайт по HTTPS (на телефоне: https://IP:5173). Без HTTPS браузер блокирует геолокацию.";
  }
  return null;
}

function mapGeolocationError(error: GeolocationPositionError): GeolocationError {
  if (error.code === error.PERMISSION_DENIED) {
    return new GeolocationError(
      "Доступ к геолокации запрещён. Разрешите его в настройках браузера и устройства.",
      "denied",
    );
  }
  if (error.code === error.POSITION_UNAVAILABLE) {
    return new GeolocationError(
      "Не удалось определить местоположение. Включите GPS или Wi‑Fi.",
      "position",
    );
  }
  return new GeolocationError("Превышено время ожидания геолокации. Попробуйте ещё раз.", "timeout");
}

function readPosition(options: PositionOptions, hardTimeoutMs: number): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const settle = (fn: () => void) => {
      if (settled) {
        return;
      }
      settled = true;
      window.clearTimeout(timer);
      fn();
    };

    const timer = window.setTimeout(() => {
      settle(() => {
        reject(
          new GeolocationError(
            "Геолокация не отвечает. Проверьте GPS и разрешение для сайта в настройках.",
            "timeout",
          ),
        );
      });
    }, hardTimeoutMs);

    navigator.geolocation.getCurrentPosition(
      (position) => settle(() => resolve(position)),
      (error) => settle(() => reject(mapGeolocationError(error))),
      options,
    );
  });
}

async function ensureGeolocationPermission(): Promise<void> {
  if (!navigator.permissions?.query) {
    return;
  }
  try {
    const status = await navigator.permissions.query({ name: "geolocation" });
    if (status.state === "denied") {
      throw new GeolocationError(
        "Доступ к геолокации запрещён. Разрешите его в настройках браузера и устройства.",
        "denied",
      );
    }
  } catch (error) {
    if (error instanceof GeolocationError) {
      throw error;
    }
  }
}

export async function requestUserLocation(): Promise<{ lat: number; lon: number }> {
  const unavailable = geolocationUnavailableMessage();
  if (unavailable) {
    throw new GeolocationError(unavailable, "insecure");
  }

  await ensureGeolocationPermission();

  const attempts: PositionOptions[] = [
    { enableHighAccuracy: false, timeout: 7_000, maximumAge: 300_000 },
    { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 },
  ];

  let lastError: GeolocationError | null = null;
  for (const options of attempts) {
    try {
      const position = await readPosition(options, (options.timeout ?? 7_000) + 2_000);
      return {
        lat: position.coords.latitude,
        lon: position.coords.longitude,
      };
    } catch (error) {
      lastError =
        error instanceof GeolocationError ? error : new GeolocationError("Не удалось определить местоположение");
      if (lastError.code === "denied" || lastError.code === "insecure") {
        throw lastError;
      }
    }
  }

  throw lastError ?? new GeolocationError("Не удалось определить местоположение");
}
