/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  readonly VITE_TP_BOOKING_WIDGET_HTML?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
