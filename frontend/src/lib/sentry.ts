/**
 * Sentry 前端集成
 *
 * 提供前端错误监控和性能追踪功能
 */

import { useEffect } from 'react'

import { createRoutesFromChildren, matchRoutes, useLocation, useNavigationType } from 'react-router'

/** React Router v6 的 router 实例（createBrowserRouter 等返回），由 Sentry 集成使用 */
type ReactRouterV6Router = unknown

// Sentry 类型定义（在运行时动态加载，避免依赖问题）
interface SentryInit {
  dsn: string
  environment?: string
  tracesSampleRate?: number
  replaysSessionSampleRate?: number
  replaysOnErrorSampleRate?: number
  integrations?: unknown[]
  beforeSend?: (event: SentryEvent) => SentryEvent | null
  beforeBreadcrumb?: (breadcrumb: SentryBreadcrumb) => SentryBreadcrumb | null
}

interface SentryEvent {
  request?: {
    headers?: Record<string, string>
  }
  user?: {
    id?: string
    email?: string
  }
  tags?: Record<string, string>
}

interface SentryBreadcrumb {
  category?: string
  message?: string
  level?: string
  data?: Record<string, unknown>
}

interface SentryClient {
  init: (config: SentryInit) => void
  captureException: (error: Error) => void
  captureMessage: (message: string, level: string) => void
  setUser: (user?: { id?: string; email?: string } | null) => void
  setTag: (key: string, value: string) => void
  setContext: (key: string, context: Record<string, unknown>) => void
  addBreadcrumb: (breadcrumb: SentryBreadcrumb) => void
  withScope: (callback: (scope: SentryScope) => void) => void
  browserTracingIntegration: () => unknown
  replayIntegration: (options?: { maskAllText?: boolean; blockAllMedia?: boolean }) => unknown
  reactRouterV6BrowserTracingIntegration: (
    router: ReactRouterV6Router,
    options: {
      useEffect: typeof useEffect
      useLocation: typeof useLocation
      useNavigationType: typeof useNavigationType
      createRoutesFromChildren: typeof createRoutesFromChildren
      matchRoutes: typeof matchRoutes
    }
  ) => unknown
}

interface SentryScope {
  setTag: (key: string, value: string) => void
  setExtra: (key: string, value: unknown) => void
  setUser: (user: { id?: string; email?: string }) => void
}

// Sentry 初始化状态
let isInitialized = false
let sentryClient: SentryClient | null = null

/**
 * 从环境变量获取 Sentry DSN
 */
function getSentryDsn(): string {
  // VITE_SENTRY_DSN 在 vite-env.d.ts 中声明，ESLint 仍将 env 推断为 any
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return -- 见上
  return import.meta.env.VITE_SENTRY_DSN ?? ''
}

/**
 * 获取环境名称
 */
function getSentryEnvironment(): string {
  const mode = import.meta.env.MODE
  if (mode === 'production') return 'production'
  if (mode === 'staging') return 'staging'
  return 'development'
}

const SENSITIVE_HEADERS = ['authorization', 'cookie', 'x-api-key', 'x-auth-token']

/**
 * 在事件发送前过滤敏感信息
 */
function beforeSend(event: SentryEvent): SentryEvent | null {
  if (event.request?.headers) {
    const filtered: Record<string, string> = {}
    for (const [k, v] of Object.entries(event.request.headers)) {
      if (!SENSITIVE_HEADERS.includes(k.toLowerCase())) {
        filtered[k] = v
      }
    }
    event.request.headers = filtered
  }

  return event
}

/**
 * 在面包屑发送前过滤
 */
function beforeBreadcrumb(breadcrumb: SentryBreadcrumb): SentryBreadcrumb | null {
  // 过滤掉某些不需要的面包屑
  if (breadcrumb.category === 'xhr') {
    // 可以在这里过滤敏感的 API 调用
    const url = breadcrumb.data?.url as string | undefined
    if (url?.includes('/api/v1/auth/')) {
      // 过滤掉认证相关的 API 调用日志
      return null
    }
  }

  return breadcrumb
}

/**
 * 动态加载 Sentry SDK（v10 使用 browserTracingIntegration / replayIntegration）
 */
async function loadSentry(): Promise<SentryClient | null> {
  if (sentryClient) {
    return sentryClient
  }

  try {
    const SentryModule = await import('@sentry/react')
    sentryClient = SentryModule.default as SentryClient
    return sentryClient
  } catch (error) {
    console.error('Failed to load Sentry:', error)
    return null
  }
}

/**
 * 初始化 Sentry
 */
export async function initSentry(options?: Partial<SentryInit>): Promise<boolean> {
  const dsn = getSentryDsn()

  if (!dsn) {
    // 初始化阶段尚未有 logger，使用 console 输出配置状态
    // eslint-disable-next-line no-console -- Sentry 初始化状态日志
    console.log('Sentry DSN not configured, skipping initialization')
    return false
  }

  if (isInitialized) {
    console.warn('Sentry already initialized')
    return true
  }

  try {
    const Sentry = await loadSentry()
    if (!Sentry) {
      return false
    }

    Sentry.init({
      dsn,
      environment: getSentryEnvironment(),
      tracesSampleRate: options?.tracesSampleRate ?? 0.1,
      replaysSessionSampleRate: options?.replaysSessionSampleRate ?? 0.0, // 生产环境可设为 0.1
      replaysOnErrorSampleRate: options?.replaysOnErrorSampleRate ?? 1.0,
      integrations: options?.integrations ?? [
        Sentry.browserTracingIntegration(),
        Sentry.replayIntegration({
          maskAllText: true,
          blockAllMedia: true,
        }),
      ],
      beforeSend,
      beforeBreadcrumb,
      ...options,
    })

    // 将 Sentry 挂载到 window，供 logger.ts 使用
    if (typeof window !== 'undefined') {
      ;(window as { Sentry?: SentryClient }).Sentry = Sentry
    }

    isInitialized = true
    // eslint-disable-next-line no-console -- Sentry 初始化成功日志
    console.log(`Sentry initialized: environment=${getSentryEnvironment()}`)

    return true
  } catch (error) {
    console.error('Failed to initialize Sentry:', error)
    return false
  }
}

/**
 * 检查 Sentry 是否已初始化
 */
export function isSentryInitialized(): boolean {
  return isInitialized
}

/**
 * 捕获异常并发送到 Sentry
 */
export function captureException(error: Error): void {
  if (sentryClient) {
    sentryClient.captureException(error)
  }
}

/**
 * 捕获消息并发送到 Sentry
 */
export function captureMessage(message: string, level: string = 'info'): void {
  if (sentryClient) {
    sentryClient.captureMessage(message, level)
  }
}

/**
 * 设置用户上下文
 */
export function setUser(user: { id?: string; email?: string }): void {
  if (sentryClient) {
    sentryClient.setUser(user)
  }
}

/**
 * 清除用户上下文
 */
export function clearUser(): void {
  if (sentryClient) {
    sentryClient.setUser(null)
  }
}

/**
 * 设置标签
 */
export function setTag(key: string, value: string): void {
  if (sentryClient) {
    sentryClient.setTag(key, value)
  }
}

/**
 * 设置上下文
 */
export function setContext(key: string, context: Record<string, unknown>): void {
  if (sentryClient) {
    sentryClient.setContext(key, context)
  }
}

/**
 * 添加面包屑
 */
export function addBreadcrumb(breadcrumb: SentryBreadcrumb): void {
  if (sentryClient) {
    sentryClient.addBreadcrumb(breadcrumb)
  }
}

/**
 * 创建 React Router v6 集成
 */
export function createReactRouterV6Integration(router: ReactRouterV6Router) {
  return async () => {
    const Sentry = await loadSentry()
    if (!Sentry) {
      return null
    }
    return Sentry.reactRouterV6BrowserTracingIntegration(router, {
      useEffect,
      useLocation,
      useNavigationType,
      createRoutesFromChildren,
      matchRoutes,
    })
  }
}

// 导出类型
export type { SentryEvent, SentryBreadcrumb, SentryClient }
