import { useCallback, useEffect, useRef, useState } from "react";

const SCRIPT_SRC =
  "https://smartcaptcha.cloud.yandex.ru/captcha.js?render=onload&onload=__smartCaptchaOnLoad";

/** Контейнер в layout, но невидим — `display:none` ломает render/execute. */
export const SMART_CAPTCHA_CONTAINER_CLASS =
  "pointer-events-none fixed bottom-0 right-0 h-px w-px overflow-hidden opacity-0";

let scriptPromise: Promise<void> | null = null;

function clientKey(): string {
  return (import.meta.env.VITE_YANDEX_SMARTCAPTCHA_CLIENT_KEY ?? "").trim();
}

function captchaTestMode(): boolean {
  return import.meta.env.VITE_YANDEX_SMARTCAPTCHA_TEST?.trim() === "true";
}

function loadSmartCaptchaScript(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("CAPTCHA недоступна"));
  }
  if (window.smartCaptcha) {
    return Promise.resolve();
  }
  if (scriptPromise) {
    return scriptPromise;
  }
  scriptPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector(`script[src^="${SCRIPT_SRC.split("?")[0]}"]`);
    if (existing) {
      if (window.smartCaptcha) {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("CAPTCHA script error")), {
        once: true,
      });
      return;
    }
    (window as Window & { __smartCaptchaOnLoad?: () => void }).__smartCaptchaOnLoad = () =>
      resolve();
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.defer = true;
    script.onerror = () => reject(new Error("CAPTCHA script error"));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export function smartCaptchaClientKey(): string {
  return clientKey();
}

export function useYandexSmartCaptcha(initWidget: boolean) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<number | null>(null);
  const pendingRef = useRef<{
    resolve: (token: string) => void;
    reject: (error: Error) => void;
  } | null>(null);
  const readyResolveRef = useRef<(() => void) | null>(null);
  const readyPromiseRef = useRef<Promise<void> | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!initWidget || !clientKey()) {
      setReady(false);
      widgetIdRef.current = null;
      readyPromiseRef.current = null;
      readyResolveRef.current = null;
      return;
    }

    let cancelled = false;
    readyPromiseRef.current = new Promise<void>((resolve) => {
      readyResolveRef.current = resolve;
    });

    void loadSmartCaptchaScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.smartCaptcha) {
          return;
        }
        widgetIdRef.current = window.smartCaptcha.render(containerRef.current, {
          sitekey: clientKey(),
          invisible: true,
          test: captchaTestMode(),
          hl: "ru",
          shieldPosition: "bottom-right",
          callback: (token: string) => {
            const pending = pendingRef.current;
            pendingRef.current = null;
            if (pending && token) {
              pending.resolve(token);
            }
          },
        });
        setReady(true);
        readyResolveRef.current?.();
      })
      .catch(() => {
        if (!cancelled) {
          setReady(false);
          readyResolveRef.current?.();
        }
      });

    return () => {
      cancelled = true;
      pendingRef.current?.reject(new Error("CAPTCHA сброшена"));
      pendingRef.current = null;
    };
  }, [initWidget]);

  const waitUntilReady = useCallback(async (timeoutMs = 15_000): Promise<void> => {
    if (ready && window.smartCaptcha && widgetIdRef.current != null) {
      return;
    }
    const pending = readyPromiseRef.current;
    if (!pending) {
      throw new Error("CAPTCHA не инициализирована");
    }
    await Promise.race([
      pending,
      new Promise<void>((_, reject) => {
        window.setTimeout(
          () => reject(new Error("CAPTCHA не загрузилась. Обновите страницу и попробуйте снова.")),
          timeoutMs,
        );
      }),
    ]);
    if (!window.smartCaptcha || widgetIdRef.current == null) {
      throw new Error("CAPTCHA не загрузилась. Обновите страницу и попробуйте снова.");
    }
  }, [ready]);

  const requestToken = useCallback(async (): Promise<string> => {
    if (!initWidget || !clientKey()) {
      throw new Error("CAPTCHA не настроена");
    }
    await waitUntilReady();
    return new Promise<string>((resolve, reject) => {
      pendingRef.current = { resolve, reject };
      try {
        window.smartCaptcha!.execute(widgetIdRef.current!);
      } catch (err) {
        pendingRef.current = null;
        reject(err instanceof Error ? err : new Error("CAPTCHA execute failed"));
      }
    });
  }, [initWidget, waitUntilReady]);

  const resetToken = useCallback(() => {
    pendingRef.current = null;
    if (window.smartCaptcha && widgetIdRef.current != null) {
      window.smartCaptcha.reset(widgetIdRef.current);
    }
  }, []);

  return { containerRef, ready, requestToken, resetToken };
}
