/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  readonly VITE_TP_YANDEX_TRAVEL_WIDGET_SRC?: string;
  readonly VITE_YANDEX_METRIKA_ID?: string;
  readonly VITE_YANDEX_SMARTCAPTCHA_CLIENT_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
