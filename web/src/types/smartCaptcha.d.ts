interface SmartCaptchaRenderOptions {
  sitekey: string;
  invisible?: boolean;
  test?: boolean;
  callback?: (token: string) => void;
  shieldPosition?: string;
  hideShield?: boolean;
  hl?: string;
}

interface SmartCaptchaApi {
  render(container: HTMLElement | string, options: SmartCaptchaRenderOptions): number;
  execute(widgetId?: number): void;
  getResponse(widgetId?: number): string;
  reset(widgetId?: number): void;
}

interface Window {
  smartCaptcha?: SmartCaptchaApi;
}
