/**
 * 内置工具多选组件
 *
 * 按类别分组展示内置工具，供 Agent 配置时选择可用工具。
 */

import { useQuery } from '@tanstack/react-query'

import { toolsApi, type ToolDefinition } from '@/api/tools'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

/** 类别显示名称 */
const CATEGORY_LABELS: Record<string, string> = {
  file: '文件操作',
  code: '代码执行',
  search: '搜索',
  database: '数据库',
  network: '网络',
  system: '系统',
  external: '外部',
}

function groupByCategory(tools: ToolDefinition[]): Map<string, ToolDefinition[]> {
  const map = new Map<string, ToolDefinition[]>()
  for (const tool of tools) {
    const cat = tool.category ?? 'system'
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(tool)
  }
  return map
}

interface ToolSelectorProps {
  value: string[]
  onChange: (value: string[]) => void
  disabled?: boolean
  className?: string
}

export function ToolSelector({
  value,
  onChange,
  disabled = false,
  className,
}: Readonly<ToolSelectorProps>): React.JSX.Element {
  const { data: tools = [], isLoading, error } = useQuery({
    queryKey: ['built-in-tools'],
    queryFn: () => toolsApi.list(),
  })

  const selectedSet = new Set(value)

  const toggle = (name: string, checked: boolean): void => {
    if (checked) {
      onChange([...value, name])
    } else {
      onChange(value.filter((n) => n !== name))
    }
  }

  const toggleGroup = (categoryTools: ToolDefinition[], checked: boolean): void => {
    const names = categoryTools.map((t) => t.name)
    if (checked) {
      const added = new Set([...value, ...names])
      onChange(Array.from(added))
    } else {
      onChange(value.filter((n) => !names.includes(n)))
    }
  }

  if (isLoading) {
    return (
      <div className={cn('rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground', className)}>
        加载工具列表中...
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn('rounded-md border border-destructive/50 bg-destructive/5 p-4 text-center text-sm text-destructive', className)}>
        加载失败，请稍后重试
      </div>
    )
  }

  if (tools.length === 0) {
    return (
      <div className={cn('rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground', className)}>
        暂无内置工具
      </div>
    )
  }

  const byCategory = groupByCategory(tools)
  const orderedCategories = ['code', 'file', 'search', 'database', 'network', 'system', 'external'].filter((c) =>
    byCategory.has(c)
  )
  const restCategories = Array.from(byCategory.keys()).filter((c) => !orderedCategories.includes(c))
  const categoryOrder = [...orderedCategories, ...restCategories]

  return (
    <ScrollArea className={cn('h-[280px] rounded-md border', className)}>
      <div className="space-y-4 p-3">
        {categoryOrder.map((category) => {
          const categoryTools = byCategory.get(category) ?? []
          const label = CATEGORY_LABELS[category] ?? category
          const allSelected = categoryTools.every((t) => selectedSet.has(t.name))
          const someSelected = categoryTools.some((t) => selectedSet.has(t.name))

          return (
            <div key={category} className="space-y-2">
              <div className="flex items-center gap-2">
                <Checkbox
                  id={`cat-${category}`}
                  checked={allSelected ? true : someSelected ? 'indeterminate' : false}
                  onCheckedChange={(checked) => {
                    toggleGroup(categoryTools, checked === true)
                  }}
                  disabled={disabled}
                  className="shrink-0"
                />
                <label
                  htmlFor={`cat-${category}`}
                  className="text-sm font-medium cursor-pointer select-none"
                >
                  {label}
                </label>
              </div>
              <ul className="ml-6 space-y-1.5">
                {categoryTools.map((tool) => (
                  <li key={tool.name} className="flex items-start gap-2">
                    <Checkbox
                      id={`tool-${tool.name}`}
                      checked={selectedSet.has(tool.name)}
                      onCheckedChange={(checked) => {
                        toggle(tool.name, checked === true)
                      }}
                      disabled={disabled}
                      className="mt-0.5 shrink-0"
                    />
                    <label
                      htmlFor={`tool-${tool.name}`}
                      className="cursor-pointer select-none text-sm leading-tight"
                    >
                      <span className="font-mono font-medium">{tool.name}</span>
                      <span className="ml-1.5 text-muted-foreground">
                        — {tool.description || '无描述'}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}
