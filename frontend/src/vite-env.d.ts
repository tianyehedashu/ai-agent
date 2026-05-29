/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_APP_ROOT: string
  readonly VITE_AUTH_MODE?: string
  readonly VITE_SSO_LOGIN_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
