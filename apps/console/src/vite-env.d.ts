interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_STAFF_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
