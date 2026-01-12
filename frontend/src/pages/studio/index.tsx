/**
 * Studio Page - 工作台页面
 *
 * 实现 Code-First 可视化编排
 */

import { useState, useCallback, useEffect } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  Node,
  Edge,
  Connection,
  addEdge,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import Editor from '@monaco-editor/react'
import {
  Play,
  Save,
  Code,
  LayoutGrid,
  RefreshCw,
  PlusCircle,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { LLMNode, ToolNode, ConditionNode, CustomNode } from './components/nodes'

// 节点类型映射
const nodeTypes = {
  llm: LLMNode,
  tool: ToolNode,
  condition: ConditionNode,
  custom: CustomNode,
}

// 初始节点和边 (示例)
const initialNodes: Node[] = [
  {
    id: 'process_input',
    type: 'custom',
    position: { x: 50, y: 50 },
    data: { label: 'Process Input', nodeType: 'custom', function: 'process_input' },
  },
  {
    id: 'llm_call',
    type: 'llm',
    position: { x: 300, y: 50 },
    data: { label: 'LLM Call', nodeType: 'llm', function: 'call_llm' },
  },
  {
    id: 'generate_response',
    type: 'custom',
    position: { x: 550, y: 50 },
    data: { label: 'Generate Response', nodeType: 'custom', function: 'generate_response' },
  },
]

const initialEdges: Edge[] = [
  { id: 'e1', source: 'process_input', target: 'llm_call', type: 'smoothstep' },
  { id: 'e2', source: 'llm_call', target: 'generate_response', type: 'smoothstep' },
]

const defaultCode = `"""
Agent Workflow

使用 LangGraph 定义的 Agent 工作流
"""

from typing import TypedDict, Sequence
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    """Agent 状态"""
    messages: Sequence[dict]
    next_action: str


# ========== 节点函数 ==========

def process_input(state: AgentState):
    """处理输入"""
    return state


def call_llm(state: AgentState):
    """调用 LLM"""
    return state


def generate_response(state: AgentState):
    """生成响应"""
    return state


# ========== 图定义 ==========

graph = StateGraph(AgentState)

# 添加节点
graph.add_node("process_input", process_input)
graph.add_node("llm_call", call_llm)
graph.add_node("generate_response", generate_response)

# 添加边
graph.add_edge("process_input", "llm_call")
graph.add_edge("llm_call", "generate_response")
graph.add_edge("generate_response", END)

# 设置入口点
graph.set_entry_point("process_input")

# 编译图
app = graph.compile()
`

export default function StudioPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [code, setCode] = useState(defaultCode)
  const [activeView, setActiveView] = useState<'split' | 'code' | 'canvas'>('split')
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [isLoading, setIsLoading] = useState(false)

  // 连接边
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, type: 'smoothstep' }, eds))
    },
    [setEdges]
  )

  // 从代码解析节点和边
  const parseCode = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/v1/studio/workflows/temp/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      })
      const data = await response.json()

      if (data.nodes && data.edges) {
        setNodes(data.nodes)
        setEdges(data.edges)
      }
    } catch (error) {
      console.error('Parse error:', error)
    } finally {
      setIsLoading(false)
    }
  }, [code, setNodes, setEdges])

  // 从画布生成代码
  const generateCode = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/v1/studio/workflows/temp/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges }),
      })
      const data = await response.json()

      if (data.code) {
        setCode(data.code)
      }
    } catch (error) {
      console.error('Generate error:', error)
    } finally {
      setIsLoading(false)
    }
  }, [nodes, edges])

  // 运行测试
  const runTest = useCallback(async () => {
    setIsLoading(true)
    try {
      // TODO: 实现测试运行
      console.log('Running test...')
    } finally {
      setIsLoading(false)
    }
  }, [])

  return (
    <div className="flex h-full overflow-hidden bg-background">
      {/* 侧边栏 - 工作流列表 */}
      <div
        className={cn(
          'border-r bg-muted/30 transition-all duration-300',
          isSidebarOpen ? 'w-64' : 'w-0'
        )}
      >
        {isSidebarOpen && (
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b p-4">
              <h2 className="font-semibold">工作流</h2>
              <Button variant="ghost" size="icon">
                <PlusCircle className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex-1 overflow-auto p-2">
              {/* 工作流列表 */}
              <div className="space-y-1">
                <div className="rounded-md bg-primary/10 p-2 text-sm font-medium">
                  My Agent Workflow
                </div>
                <div className="rounded-md p-2 text-sm text-muted-foreground hover:bg-muted">
                  Customer Service Bot
                </div>
                <div className="rounded-md p-2 text-sm text-muted-foreground hover:bg-muted">
                  Data Pipeline
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 主编辑区域 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 工具栏 */}
        <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            >
              {isSidebarOpen ? (
                <ChevronLeft className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>

            <div className="h-4 w-px bg-border" />

            {/* 视图切换 */}
            <div className="flex rounded-md bg-muted p-1">
              <Button
                variant={activeView === 'split' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setActiveView('split')}
              >
                <LayoutGrid className="mr-1 h-4 w-4" />
                分屏
              </Button>
              <Button
                variant={activeView === 'code' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setActiveView('code')}
              >
                <Code className="mr-1 h-4 w-4" />
                代码
              </Button>
              <Button
                variant={activeView === 'canvas' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setActiveView('canvas')}
              >
                <LayoutGrid className="mr-1 h-4 w-4" />
                画布
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={parseCode}
              disabled={isLoading}
            >
              <RefreshCw className={cn('mr-1 h-4 w-4', isLoading && 'animate-spin')} />
              同步到画布
            </Button>
            <Button variant="outline" size="sm" onClick={generateCode} disabled={isLoading}>
              <Code className="mr-1 h-4 w-4" />
              生成代码
            </Button>
            <Button variant="outline" size="sm">
              <Save className="mr-1 h-4 w-4" />
              保存
            </Button>
            <Button size="sm" onClick={runTest} disabled={isLoading}>
              <Play className="mr-1 h-4 w-4" />
              运行
            </Button>
          </div>
        </div>

        {/* 编辑区域 */}
        <div className="flex flex-1 overflow-hidden">
          {/* 代码编辑器 */}
          {(activeView === 'split' || activeView === 'code') && (
            <div
              className={cn(
                'flex flex-col overflow-hidden border-r',
                activeView === 'split' ? 'w-1/2' : 'w-full'
              )}
            >
              <Editor
                height="100%"
                defaultLanguage="python"
                value={code}
                onChange={(value) => setCode(value || '')}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  lineNumbers: 'on',
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                  tabSize: 4,
                }}
              />
            </div>
          )}

          {/* React Flow 画布 */}
          {(activeView === 'split' || activeView === 'canvas') && (
            <div
              className={cn(
                'flex flex-col',
                activeView === 'split' ? 'w-1/2' : 'w-full'
              )}
            >
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
              >
                <Controls />
                <MiniMap />
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
              </ReactFlow>
            </div>
          )}
        </div>

        {/* 底部面板 - 测试输出 */}
        <div className="h-48 border-t bg-muted/30">
          <Tabs defaultValue="output" className="h-full">
            <div className="flex items-center justify-between border-b px-4">
              <TabsList className="h-10">
                <TabsTrigger value="output">输出</TabsTrigger>
                <TabsTrigger value="logs">日志</TabsTrigger>
                <TabsTrigger value="variables">变量</TabsTrigger>
              </TabsList>
              <Button variant="ghost" size="sm">
                <Settings className="h-4 w-4" />
              </Button>
            </div>
            <TabsContent value="output" className="h-[calc(100%-40px)] p-4">
              <pre className="h-full overflow-auto rounded bg-muted p-2 font-mono text-sm">
                {/* 输出内容 */}
                准备就绪。点击"运行"开始测试。
              </pre>
            </TabsContent>
            <TabsContent value="logs" className="h-[calc(100%-40px)] p-4">
              <pre className="h-full overflow-auto rounded bg-muted p-2 font-mono text-sm text-muted-foreground">
                等待执行...
              </pre>
            </TabsContent>
            <TabsContent value="variables" className="h-[calc(100%-40px)] p-4">
              <div className="text-sm text-muted-foreground">
                执行后将显示状态变量
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
