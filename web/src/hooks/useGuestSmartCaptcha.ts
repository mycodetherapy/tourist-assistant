import { useQuery } from "@tanstack/react-query";
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
  const captcha = useYandexSmartCaptcha(enabled);

  return {
    ...captcha,
    enabled,
    loading: configQuery.isLoading,
  };
}
