/** compact / full 凭据表格列数（与 ManagedCredentialsTableHead 列定义同步）。 */

export function compactCredentialTableColCount(showAffiliation: boolean): number {
  // 名称 | API Key | 提供商 | [归属] | 提供者 | 启用 | 操作
  return showAffiliation ? 7 : 6
}

export function fullCredentialTableColCount(showAffiliation: boolean): number {
  // 名称 | API Key | 提供商 | 作用域 | [归属] | 提供者 | api_base | 启用 | 操作
  return showAffiliation ? 9 : 8
}
