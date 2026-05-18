/** bundle-preload：注册表单 chunk（无 workspace 依赖，避免循环引用） */

export function preloadRegisterModelForm(): void {
  void import('./register-model-form')
}
