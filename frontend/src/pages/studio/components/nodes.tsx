/**
 * Custom Nodes - React Flow 自定义节点
 */

import { memo } from 'react'

import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Bot, Wrench, GitBranch, Box } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface NodeData {
  label: string
  nodeType: string
  function?: string
  [key: string]: unknown
}

// 基础节点样式
const baseNodeStyle = 'px-4 py-3 rounded-lg border-2 shadow-sm min-w-[150px]'

// LLM 节点
export const LLMNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as NodeData
  return (
    <div
      className={cn(
        baseNodeStyle,
        'border-sky-400 bg-sky-50',
        selected ? 'ring-2 ring-sky-500 ring-offset-2' : undefined
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-3 !w-3 !bg-sky-500" />

      <div className="flex items-center gap-2">
        <div className="rounded-md bg-sky-100 p-1.5">
          <Bot className="h-4 w-4 text-sky-600" />
        </div>
        <div>
          <div className="text-sm font-medium text-sky-900">{nodeData.label}</div>
          {nodeData.function && (
            <div className="font-mono text-xs text-sky-600">{nodeData.function}</div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!h-3 !w-3 !bg-sky-500" />
    </div>
  )
})

LLMNode.displayName = 'LLMNode'

// 工具节点
export const ToolNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as NodeData
  return (
    <div
      className={cn(
        baseNodeStyle,
        'border-amber-400 bg-amber-50',
        selected ? 'ring-2 ring-amber-500 ring-offset-2' : undefined
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-3 !w-3 !bg-amber-500" />

      <div className="flex items-center gap-2">
        <div className="rounded-md bg-amber-100 p-1.5">
          <Wrench className="h-4 w-4 text-amber-600" />
        </div>
        <div>
          <div className="text-sm font-medium text-amber-900">{nodeData.label}</div>
          {nodeData.function && (
            <div className="font-mono text-xs text-amber-600">{nodeData.function}</div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!h-3 !w-3 !bg-amber-500" />
    </div>
  )
})

ToolNode.displayName = 'ToolNode'

// 条件节点
export const ConditionNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as NodeData
  return (
    <div
      className={cn(
        baseNodeStyle,
        'border-purple-400 bg-purple-50',
        selected ? 'ring-2 ring-purple-500 ring-offset-2' : undefined
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-3 !w-3 !bg-purple-500" />

      <div className="flex items-center gap-2">
        <div className="rounded-md bg-purple-100 p-1.5">
          <GitBranch className="h-4 w-4 text-purple-600" />
        </div>
        <div>
          <div className="text-sm font-medium text-purple-900">{nodeData.label}</div>
          {nodeData.function && (
            <div className="font-mono text-xs text-purple-600">{nodeData.function}</div>
          )}
        </div>
      </div>

      {/* 条件节点有多个输出 */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        style={{ top: '30%' }}
        className="!h-3 !w-3 !bg-green-500"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        style={{ top: '70%' }}
        className="!h-3 !w-3 !bg-red-500"
      />
    </div>
  )
})

ConditionNode.displayName = 'ConditionNode'

// 自定义节点
export const CustomNode = memo(({ data, selected }: NodeProps) => {
  const nodeData = data as NodeData
  return (
    <div
      className={cn(
        baseNodeStyle,
        'border-slate-400 bg-slate-50',
        selected ? 'ring-2 ring-slate-500 ring-offset-2' : undefined
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-3 !w-3 !bg-slate-500" />

      <div className="flex items-center gap-2">
        <div className="rounded-md bg-slate-100 p-1.5">
          <Box className="h-4 w-4 text-slate-600" />
        </div>
        <div>
          <div className="text-sm font-medium text-slate-900">{nodeData.label}</div>
          {nodeData.function && (
            <div className="font-mono text-xs text-slate-600">{nodeData.function}</div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!h-3 !w-3 !bg-slate-500" />
    </div>
  )
})

CustomNode.displayName = 'CustomNode'
