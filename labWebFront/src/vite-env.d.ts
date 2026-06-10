/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_COMPRAS_URL?: string;
  readonly VITE_SUGESTOES_URL?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
