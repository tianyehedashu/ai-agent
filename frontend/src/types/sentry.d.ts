/**
 * @sentry/react 模块声明
 *
 * Sentry 在 sentry.ts 中通过动态 import 加载，若未安装则运行时 catch 处理。
 * 此声明文件仅用于满足 TypeScript 编译，避免 TS2307 错误。
 */
declare module '@sentry/react' {
  const Sentry: unknown
  export default Sentry
}
