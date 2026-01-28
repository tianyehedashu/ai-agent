/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_SENTRY_DSN?: string
}

// 全局类型声明，供 Vite 与 import.meta 使用
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- 全局声明，由 TS 使用
interface ImportMeta {
  readonly env: ImportMetaEnv
}

/** Sentry 由 sentry.ts 挂载到 window，供 logger 等使用 */
declare global {
  interface Window {
    Sentry?: {
      captureException: (error: Error, options?: { extra?: Record<string, unknown> }) => void
      captureMessage: (
        message: string,
        options?: { level?: string; extra?: Record<string, unknown> }
      ) => void
      withScope: (fn: (scope: { setTag: (k: string, v: string) => void }) => void) => void
    }
  }
}

export {}
