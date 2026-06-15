/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  readonly VITE_TP_YANDEX_TRAVEL_WIDGET_SRC?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
