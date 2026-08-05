import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { guestClient } from "../api/guest";
import { smartCaptchaClientKey, useYandexSmartCaptcha } from "../hooks/useYandexSmartCaptcha";

export async function fetchGuestCaptchaConfig(): Promise<{ smart_captcha_enabled: boolean }> {
  const { data } = await guestClient.get<{ smart_captcha_enabled: boolean }>("/captcha-config");
  return data;
}

export function useGuestSmartCaptcha() {
  const configQuery = useQuery({
    queryKey: ["guest", "captcha-config"],
    queryFn: fetchGuestCaptchaConfig,
    staleTime: 60_000,
  });
  const clientKey = smartCaptchaClientKey();
  const serverEnabled = Boolean(configQuery.data?.smart_captcha_enabled);
  const enabled = serverEnabled && Boolean(clientKey);
  const initWidget = Boolean(clientKey) && (serverEnabled || configQuery.isLoading);
  const captcha = useYandexSmartCaptcha(initWidget);

  const resolveCaptchaRequired = useCallback(async (): Promise<boolean> => {
    if (!clientKey) {
      return false;
    }
    if (configQuery.data != null) {
      return Boolean(configQuery.data.smart_captcha_enabled);
    }
    const config = await configQuery.refetch();
    if (config.error) {
      throw new Error("Не удалось проверить настройки CAPTCHA");
    }
    return Boolean(config.data?.smart_captcha_enabled);
  }, [clientKey, configQuery]);

  const requestTokenIfRequired = useCallback(async (): Promise<string | undefined> => {
    const required = await resolveCaptchaRequired();
    if (!required) {
      return undefined;
    }
    return captcha.requestToken();
  }, [captcha, resolveCaptchaRequired]);

  return {
    ...captcha,
    enabled,
    loading: configQuery.isLoading,
    requestTokenIfRequired,
  };
}
