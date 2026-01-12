/**
 * Custom Nodes - React Flow 自定义节点
 */

import { memo } from 'react'
import { Handle, Position, NodeProps } from '@xyflow/react'
import { Bot, Wrench, GitBranch, Box } from 'lucide-react'
import { cn } from '@/lib/utils'

interface NodeData {
  label: string
  nodeType: string
  function?: string
}

// 基础节点样式
const baseNodeStyle = 'px-4 py-3 rounded-lg border-2 shadow-sm min-w-[150px]'

// LLM 节点
export const LLMNode = memo(({ data, selected }: NodeProps<NodeData>) => {
  return (
    <div
      className={cn(
        baseNodeStyle,
        'bg-sky-50 border-sky-400',
        selected && 'ring-2 ring-sky-500 ring-offset-2'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-sky-500 !w-3 !h-3"
      />

      <div className="flex items-center gap-2">
        <div className="rounded-md bg-sky-100 p-1.5">
          <Bot className="h-4 w-4 text-sky-600" />
        </div>
        <div>
          <div className="font-medium text-sm text-sky-900">{data.label}</div>
          {data.function && (
            <div className="text-xs text-sky-600 font-mono">{data.function}</div>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!bg-sky-500 !w-3 !h-3"
      />
    </div>
  )
})

LLMNode.displayName = 'LLMNode'

// 工具节点
export const ToolNode = memo(({ data, selected }: NodeProps<NodeData>) => {
  return (
    <div
      className={cn(
        baseNodeStyle,
        'bg-amber-50 border-amber-400',
        selected && 'ring-2 ring-amber-500 ring-offset-2'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-amber-500 !w-3 !h-3"
      />

      <div className="flex items-center gap-2">
        <div className="rounded-md bg-amber-100 p-1.5">
          <Wrench className="h-4 w-4 text-amber-600" />
        </div>
        <div>
          <div className="font-medium text-sm text-amber-900">{data.label}</div>
          {data.function && (
            <div className="text-xs text-amber-600 font-mono">{data.function}</div>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!bg-amber-500 !w-3 !h-3"
      />
    </div>
  )
})

ToolNode.displayName = 'ToolNode'

// 条件节点
export const ConditionNode = memo(({ data, selected }: NodeProps<NodeData>) => {
  return (
    <div
      className={cn(
        baseNodeStyle,
        'bg-purple-50 border-purple-400',
        selected && 'ring-2 ring-purple-500 ring-offset-2'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-purple-500 !w-3 !h-3"
      />

      <div className="flex items-center gap-2">
        <div className="rounded-md bg-purple-100 p-1.5">
          <GitBranch className="h-4 w-4 text-purple-600" />
        </div>
        <div>
          <div className="font-medium text-sm text-purple-900">{data.label}</div>
          {data.function && (
            <div className="text-xs text-purple-600 font-mono">{data.function}</div>
          )}
        </div>
      </div>

      {/* 条件节点有多个输出 */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{ top: '30%' }}
        className="!bg-green-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{ top: '70%' }}
        className="!bg-red-500 !w-3 !h-3"
      />
    </div>
  )
})

ConditionNode.displayName = 'ConditionNode'

// 自定义节点
export const CustomNode = memo(({ data, selected }: NodeProps<NodeData>) => {
  return (
    <div
      className={cn(
        baseNodeStyle,
        'bg-slate-50 border-slate-400',
        selected && 'ring-2 ring-slate-500 ring-offset-2'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-slate-500 !w-3 !h-3"
      />

      <div className="flex items-center gap-2">
        <div className="rounded-md bg-slate-100 p-1.5">
          <Box className="h-4 w-4 text-slate-600" />
        </div>
        <div>
          <div className="font-medium text-sm text-slate-900">{data.label}</div>
          {data.function && (
            <div className="text-xs text-slate-600 font-mono">{data.function}</div>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!bg-slate-500 !w-3 !h-3"
      />
    </div>
  )
})

CustomNode.displayName = 'CustomNode'
