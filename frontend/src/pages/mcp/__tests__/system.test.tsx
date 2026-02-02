/**
 * 系统 MCP 页测试
 *
 * 验证「管理动态工具」「管理 Prompts」入口、动态工具/ Prompts 列表与添加对话框的 API 调用。
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import SystemMCPPage from '../system'

const mockListClientDirectServers = vi.fn()
const mockGetClientConfig = vi.fn()
const mockListDynamicTools = vi.fn()
const mockAddDynamicTool = vi.fn()
const mockDeleteDynamicTool = vi.fn()
const mockListDynamicPrompts = vi.fn()
const mockAddDynamicPrompt = vi.fn()
const mockUpdateDynamicPrompt = vi.fn()
const mockDeleteDynamicPrompt = vi.fn()

vi.mock('@/stores/user', () => ({
  useUserStore: (selector: (s: { currentUser: { role?: string } | null }) => unknown) =>
    selector({ currentUser: { id: '1', email: 'admin@test.com', name: 'Admin', is_anonymous: false, role: 'admin' } }),
}))

vi.mock('@/api/mcp', () => ({
  mcpApi: {
    listClientDirectServers: (...args: unknown[]) => mockListClientDirectServers(...args),
    getClientConfig: (...args: unknown[]) => mockGetClientConfig(...args),
    listDynamicTools: (...args: unknown[]) => mockListDynamicTools(...args),
    addDynamicTool: (...args: unknown[]) => mockAddDynamicTool(...args),
    deleteDynamicTool: (...args: unknown[]) => mockDeleteDynamicTool(...args),
    listDynamicPrompts: (...args: unknown[]) => mockListDynamicPrompts(...args),
    addDynamicPrompt: (...args: unknown[]) => mockAddDynamicPrompt(...args),
    updateDynamicPrompt: (...args: unknown[]) => mockUpdateDynamicPrompt(...args),
    deleteDynamicPrompt: (...args: unknown[]) => mockDeleteDynamicPrompt(...args),
  },
}))

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  )
}

describe('SystemMCPPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListClientDirectServers.mockResolvedValue({
      servers: [
        {
          name: 'llm-server',
          scope: 'llm-server',
          description: 'LLM server',
          tool_count: 0,
          tools: [],
          prompt_count: 0,
          prompts: [],
        },
      ],
      transport: 'Streamable HTTP',
      authentication: 'API Key',
      protocol_version: '2024-11-05',
    })
    mockGetClientConfig.mockResolvedValue({
      mcpServers: {
        'ai-agent-llm': {
          type: 'streamableHttp',
          url: 'http://test/api/v1/mcp/llm-server',
          headers: { Authorization: 'Bearer <YOUR_API_KEY>' },
        },
      },
    })
    mockListDynamicTools.mockResolvedValue([])
    mockListDynamicPrompts.mockResolvedValue([])
  })

  it('渲染系统 MCP 页并显示「管理动态工具」入口', async () => {
    renderWithProviders(<SystemMCPPage />)
    const manageButton = await screen.findByRole('button', {
      name: /管理动态工具/i,
    })
    expect(manageButton).toBeInTheDocument()
    expect(mockListClientDirectServers).toHaveBeenCalled()
  })

  it('点击「管理动态工具」后请求动态工具列表', async () => {
    renderWithProviders(<SystemMCPPage />)
    const manageButton = await screen.findByRole('button', {
      name: /管理动态工具/i,
    })
    fireEvent.click(manageButton)
    await waitFor(() => {
      expect(mockListDynamicTools).toHaveBeenCalledWith('llm-server')
    })
  })

  it('动态工具列表展示已添加的工具', async () => {
    mockListDynamicTools.mockResolvedValue([
      {
        id: '1',
        tool_key: 'my_tool',
        tool_type: 'http_call',
        config: { url: 'https://example.com' },
        description: 'My tool',
        enabled: true,
      },
    ])
    renderWithProviders(<SystemMCPPage />)
    const manageButton = await screen.findByRole('button', {
      name: /管理动态工具/i,
    })
    fireEvent.click(manageButton)
    await waitFor(() => {
      expect(mockListDynamicTools).toHaveBeenCalledWith('llm-server')
    })
    expect(await screen.findByText('my_tool')).toBeInTheDocument()
    expect(screen.getByText(/My tool/)).toBeInTheDocument()
  })

  it('添加工具对话框提交时调用 addDynamicTool', async () => {
    mockAddDynamicTool.mockResolvedValue({
      id: '2',
      tool_key: 'new_tool',
      tool_type: 'http_call',
      config: { url: 'https://api.test', method: 'GET' },
      description: 'New',
      enabled: true,
    })
    renderWithProviders(<SystemMCPPage />)
    const manageButton = await screen.findByRole('button', {
      name: /管理动态工具/i,
    })
    fireEvent.click(manageButton)
    await waitFor(() => {
      expect(mockListDynamicTools).toHaveBeenCalled()
    })
    const addButton = screen.getByRole('button', { name: /添加工具/i })
    fireEvent.click(addButton)
    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /添加动态工具/i })).toBeInTheDocument()
    })
    const dialog = screen.getByRole('dialog', { name: /添加动态工具/i })
    const keyInput = within(dialog).getByLabelText(/工具名称/i)
    const descInput = within(dialog).getByLabelText(/描述/i)
    const urlInput = within(dialog).getByLabelText(/^URL/)
    fireEvent.change(keyInput, { target: { value: 'new_tool' } })
    fireEvent.change(descInput, { target: { value: 'New' } })
    fireEvent.change(urlInput, { target: { value: 'https://api.test' } })
    const submitButton = within(dialog).getByRole('button', { name: /^添加$/ })
    fireEvent.click(submitButton)
    await waitFor(() => {
      expect(mockAddDynamicTool).toHaveBeenCalledWith('llm-server', {
        tool_key: 'new_tool',
        tool_type: 'http_call',
        config: expect.objectContaining({
          url: 'https://api.test',
          method: 'GET',
        }),
        description: 'New',
      })
    })
  })

  it('渲染系统 MCP 页并显示「管理 Prompts」入口', async () => {
    renderWithProviders(<SystemMCPPage />)
    const managePromptsButton = await screen.findByRole('button', {
      name: /管理 Prompts/i,
    })
    expect(managePromptsButton).toBeInTheDocument()
  })

  it('列表数据含 prompts 时展示 Prompts 数量与可用 Prompts 区块', async () => {
    mockListClientDirectServers.mockResolvedValue({
      servers: [
        {
          name: 'llm-server',
          scope: 'llm-server',
          description: 'LLM server',
          tool_count: 0,
          tools: [],
          prompt_count: 1,
          prompts: [
            { name: 'p1', title: 'P1', description: 'First prompt' },
          ],
        },
      ],
      transport: 'Streamable HTTP',
      authentication: 'API Key',
      protocol_version: '2024-11-05',
    })
    renderWithProviders(<SystemMCPPage />)
    await screen.findByRole('button', { name: /管理动态工具/i })
    expect(screen.getByText(/Prompts: 1/)).toBeInTheDocument()
    expect(screen.getByText('P1')).toBeInTheDocument()
  })

  it('点击「管理 Prompts」后打开 Sheet', async () => {
    renderWithProviders(<SystemMCPPage />)
    const managePromptsButton = await screen.findByRole('button', {
      name: /管理 Prompts/i,
    })
    fireEvent.click(managePromptsButton)
    await waitFor(() => {
      expect(screen.getByText(/动态 Prompts · llm-server/)).toBeInTheDocument()
    })
  })
})
