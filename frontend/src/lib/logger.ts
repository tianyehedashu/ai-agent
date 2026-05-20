/**
 * 前端日志工具
 *
 * 提供统一的日志接口，支持：
 * - 日志级别控制（DEBUG | INFO | WARN | ERROR）
 * - 环境区分（开发/生产）
 * - 结构化数据
 * - Sentry 集成
 */
/* eslint-disable no-console -- 本文件为日志实现，需使用 console 各级别输出 */

// 日志级别枚举
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

// 日志元数据接口
export interface LogMeta {
  [key: string]: unknown
}

/** window.Sentry 由 sentry.ts 挂载，此处仅声明调用所需的最小类型 */
interface WindowSentryClient {
  captureException: (error: Error, options?: { extra?: LogMeta }) => void
  captureMessage: (message: string, options?: { level?: string; extra?: LogMeta }) => void
  withScope: (fn: (scope: { setTag: (key: string, value: string) => void }) => void) => void
}

declare global {
  interface Window {
    Sentry?: WindowSentryClient
  }
}

// 日志配置
interface LoggerConfig {
  level: LogLevel
  enableConsole: boolean
  enableSentry: boolean
  context: string
}

// 获取当前环境的日志级别
function getEnvLogLevel(): LogLevel {
  const mode = import.meta.env.MODE
  if (mode === 'development' || mode === 'test') {
    return LogLevel.DEBUG
  }
  return LogLevel.ERROR // 生产环境只记录错误
}

// 默认配置
const defaultConfig: LoggerConfig = {
  level: getEnvLogLevel(),
  enableConsole: true,
  enableSentry: false, // 由 sentry.ts 控制初始化
  context: 'app',
}

// 当前配置
let config: LoggerConfig = { ...defaultConfig }

/**
 * 设置日志配置
 */
export function setLoggerConfig(newConfig: Partial<LoggerConfig>): void {
  config = { ...config, ...newConfig }
}

/**
 * 格式化日志消息
 */
function formatMessage(level: string, message: string, context?: string): string {
  const timestamp = new Date().toISOString()
  const contextStr = context ? `[${context}]` : ''
  return `${timestamp} ${level} ${contextStr} ${message}`
}

/**
 * 格式化元数据
 */
function formatMeta(meta?: LogMeta): string {
  if (!meta || Object.keys(meta).length === 0) {
    return ''
  }
  try {
    return ` ${JSON.stringify(meta)}`
  } catch {
    return ' [Unserializable meta]'
  }
}

/**
 * 核心日志函数
 */
function log(
  level: LogLevel,
  levelName: string,
  message: string,
  meta?: LogMeta,
  context?: string
): void {
  if (level < config.level) {
    return
  }

  const ctx = context ?? config.context
  const formattedMessage = formatMessage(levelName, message, ctx)

  if (!config.enableConsole) {
    return
  }

  const metaStr = formatMeta(meta)

  switch (level) {
    case LogLevel.DEBUG:
      console.debug(formattedMessage + metaStr, meta ?? undefined)
      break
    case LogLevel.INFO:
      console.info(formattedMessage + metaStr, meta ?? undefined)
      break
    case LogLevel.WARN:
      console.warn(formattedMessage + metaStr, meta ?? undefined)
      break
    case LogLevel.ERROR:
      console.error(formattedMessage + metaStr, meta ?? undefined)
      break
  }
}

/**
 * 全局日志实例
 */
export const logger = {
  /**
   * 调试级别日志
   */
  debug(message: string, meta?: LogMeta): void {
    log(LogLevel.DEBUG, 'DEBUG', message, meta)
  },

  /**
   * 信息级别日志
   */
  info(message: string, meta?: LogMeta): void {
    log(LogLevel.INFO, 'INFO', message, meta)
  },

  /**
   * 警告级别日志
   */
  warn(message: string, meta?: LogMeta): void {
    log(LogLevel.WARN, 'WARN', message, meta)
  },

  /**
   * 错误级别日志
   */
  error(message: string, error?: unknown, meta?: LogMeta): void {
    const errorMeta =
      error instanceof Error
        ? {
            ...meta,
            error: {
              name: error.name,
              message: error.message,
              stack: error.stack,
            },
          }
        : meta

    log(LogLevel.ERROR, 'ERROR', message, errorMeta)

    // 如果启用了 Sentry，发送到 Sentry（由 sentry.ts 处理）
    if (config.enableSentry && typeof window !== 'undefined' && window.Sentry) {
      const client = window.Sentry
      if (error instanceof Error) {
        client.captureException(error, { extra: meta })
      } else {
        client.captureMessage(message, {
          level: 'error',
          extra: meta,
        })
      }
    }
  },

  /**
   * 记录 API 请求
   */
  apiRequest(method: string, url: string, meta?: LogMeta): void {
    this.info(`API Request: ${method} ${url}`, {
      event_type: 'api_request',
      http_method: method,
      url,
      ...meta,
    })
  },

  /**
   * 记录 API 响应
   */
  apiResponse(
    method: string,
    url: string,
    status: number,
    durationMs: number,
    meta?: LogMeta
  ): void {
    const level = status >= 400 ? LogLevel.WARN : LogLevel.INFO
    log(
      level,
      level === LogLevel.WARN ? 'WARN' : 'INFO',
      `API Response: ${method} ${url} - ${String(status)} (${String(durationMs)}ms)`,
      {
        event_type: 'api_response',
        http_method: method,
        url,
        status_code: status,
        duration_ms: durationMs,
        ...meta,
      }
    )
  },

  /**
   * 记录 API 错误
   */
  apiError(method: string, url: string, error: unknown, meta?: LogMeta): void {
    this.error(`API Error: ${method} ${url}`, error, {
      event_type: 'api_error',
      http_method: method,
      url,
      ...meta,
    })
  },
}

/**
 * 带上下文的 Logger 类
 */
export class Logger {
  private context: string

  constructor(context: string) {
    this.context = context
  }

  debug(message: string, meta?: LogMeta): void {
    log(LogLevel.DEBUG, 'DEBUG', message, meta, this.context)
  }

  info(message: string, meta?: LogMeta): void {
    log(LogLevel.INFO, 'INFO', message, meta, this.context)
  }

  warn(message: string, meta?: LogMeta): void {
    log(LogLevel.WARN, 'WARN', message, meta, this.context)
  }

  error(message: string, error?: unknown, meta?: LogMeta): void {
    const errorMeta =
      error instanceof Error
        ? {
            ...meta,
            error: {
              name: error.name,
              message: error.message,
              stack: error.stack,
            },
          }
        : meta

    log(LogLevel.ERROR, 'ERROR', message, errorMeta, this.context)

    // 如果启用了 Sentry，发送到 Sentry
    if (config.enableSentry && typeof window !== 'undefined' && window.Sentry) {
      const client = window.Sentry
      if (error instanceof Error) {
        client.withScope((scope: { setTag: (key: string, value: string) => void }) => {
          scope.setTag('context', this.context)
          client.captureException(error, { extra: meta })
        })
      } else {
        client.withScope((scope: { setTag: (key: string, value: string) => void }) => {
          scope.setTag('context', this.context)
          client.captureMessage(message, {
            level: 'error',
            extra: meta,
          })
        })
      }
    }
  }
}

/**
 * 创建带上下文的 Logger 实例
 */
export function createLogger(context: string): Logger {
  return new Logger(context)
}

/**
 * 设置 Sentry 集成状态
 */
export function setSentryEnabled(enabled: boolean): void {
  config.enableSentry = enabled
}

/**
 * 获取当前日志级别
 */
export function getLogLevel(): LogLevel {
  return config.level
}

/**
 * 设置日志级别
 */
export function setLogLevel(level: LogLevel): void {
  config.level = level
}
