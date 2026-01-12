/**
 * Monaco Editor LSP Integration Hook
 *
 * 提供实时诊断、代码补全、悬停提示等功能
 */

import { useEffect, useRef, useCallback, useState } from 'react'

import { apiClient } from '@/api/client'

import type * as Monaco from 'monaco-editor'

export interface DiagnosticItem {
  line: number
  column: number
  endLine: number
  endColumn: number
  severity: 'error' | 'warning' | 'info' | 'hint'
  message: string
  code?: string
  source?: string
}

export interface CompletionItem {
  label: string
  kind: string
  detail?: string
  documentation?: string
  insertText: string
}

export interface HoverInfo {
  contents: string
  range?: {
    startLine: number
    startColumn: number
    endLine: number
    endColumn: number
  }
}

interface LSPResponse<T> {
  data?: T
  error?: string
}

interface UseMonacoLSPOptions {
  language?: string
  enableDiagnostics?: boolean
  enableCompletion?: boolean
  enableHover?: boolean
  debounceMs?: number
}

export function useMonacoLSP(
  editorRef: React.MutableRefObject<Monaco.editor.IStandaloneCodeEditor | null>,
  options: UseMonacoLSPOptions = {}
): {
  diagnostics: DiagnosticItem[]
  isValidating: boolean
  initializeLSP: (monaco: typeof Monaco) => void
} {
  const {
    language = 'python',
    enableDiagnostics = true,
    enableCompletion = true,
    enableHover = true,
    debounceMs = 500,
  } = options

  const [diagnostics, setDiagnostics] = useState<DiagnosticItem[]>([])
  const [isValidating, setIsValidating] = useState(false)
  const monacoRef = useRef<typeof Monaco | null>(null)
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null)
  const disposablesRef = useRef<Monaco.IDisposable[]>([])

  // 设置诊断标记
  const setDiagnosticMarkers = useCallback(
    (diagnosticItems: DiagnosticItem[]) => {
      const editor = editorRef.current
      const monaco = monacoRef.current
      if (!editor || !monaco) return

      const model = editor.getModel()
      if (!model) return

      const markers: Monaco.editor.IMarkerData[] = diagnosticItems.map((item) => ({
        severity: getSeverity(monaco, item.severity),
        startLineNumber: item.line,
        startColumn: item.column,
        endLineNumber: item.endLine,
        endColumn: item.endColumn,
        message: item.message,
        code: item.code,
        source: item.source ?? 'LSP',
      }))

      monaco.editor.setModelMarkers(model, 'lsp', markers)
      setDiagnostics(diagnosticItems)
    },
    [editorRef]
  )

  // 获取诊断信息
  const fetchDiagnostics = useCallback(
    async (code: string) => {
      if (!enableDiagnostics) return

      setIsValidating(true)
      try {
        const response = await apiClient.post<LSPResponse<DiagnosticItem[]>>(
          '/api/v1/quality/validate',
          {
            code,
            language,
            checks: ['syntax', 'type', 'lint'],
          }
        )

        if (Array.isArray(response.data)) {
          setDiagnosticMarkers(response.data)
        }
      } catch (error) {
        console.error('Failed to fetch diagnostics:', error)
      } finally {
        setIsValidating(false)
      }
    },
    [enableDiagnostics, language, setDiagnosticMarkers]
  )

  // 防抖获取诊断
  const debouncedFetchDiagnostics = useCallback(
    (code: string) => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
      debounceTimerRef.current = setTimeout(() => {
        void fetchDiagnostics(code)
      }, debounceMs)
    },
    [fetchDiagnostics, debounceMs]
  )

  // 获取代码补全
  const fetchCompletions = useCallback(
    async (code: string, position: { line: number; column: number }): Promise<CompletionItem[]> => {
      if (!enableCompletion) return []

      try {
        const response = await apiClient.post<LSPResponse<CompletionItem[]>>(
          '/api/v1/quality/completion',
          {
            code,
            language,
            line: position.line,
            column: position.column,
          }
        )

        return Array.isArray(response.data) ? response.data : []
      } catch (error) {
        console.error('Failed to fetch completions:', error)
        return []
      }
    },
    [enableCompletion, language]
  )

  // 获取悬停信息
  const fetchHoverInfo = useCallback(
    async (code: string, position: { line: number; column: number }): Promise<HoverInfo | null> => {
      if (!enableHover) return null

      try {
        const response = await apiClient.post<LSPResponse<HoverInfo>>('/api/v1/quality/hover', {
          code,
          language,
          line: position.line,
          column: position.column,
        })

        return response.data ?? null
      } catch (error) {
        console.error('Failed to fetch hover info:', error)
        return null
      }
    },
    [enableHover, language]
  )

  // 初始化 Monaco LSP
  const initializeLSP = useCallback(
    (monaco: typeof Monaco) => {
      monacoRef.current = monaco

      // 清理旧的 disposables
      disposablesRef.current.forEach((d) => {
        d.dispose()
      })
      disposablesRef.current = []

      // 注册补全提供者
      if (enableCompletion) {
        const completionProvider = monaco.languages.registerCompletionItemProvider(language, {
          triggerCharacters: ['.', '(', '[', '{', ' ', '"', "'"],
          provideCompletionItems: async (model, position) => {
            const code = model.getValue()
            const items = await fetchCompletions(code, {
              line: position.lineNumber,
              column: position.column,
            })

            return {
              suggestions: items.map((item) => ({
                label: item.label,
                kind: getCompletionKind(monaco, item.kind),
                detail: item.detail,
                documentation: item.documentation,
                insertText: item.insertText,
                range: {
                  startLineNumber: position.lineNumber,
                  startColumn: position.column,
                  endLineNumber: position.lineNumber,
                  endColumn: position.column,
                },
              })),
            }
          },
        })
        disposablesRef.current.push(completionProvider)
      }

      // 注册悬停提供者
      if (enableHover) {
        const hoverProvider = monaco.languages.registerHoverProvider(language, {
          provideHover: async (model, position) => {
            const code = model.getValue()
            const info = await fetchHoverInfo(code, {
              line: position.lineNumber,
              column: position.column,
            })

            if (!info) return null

            return {
              contents: [{ value: info.contents }],
              range: info.range
                ? new monaco.Range(
                    info.range.startLine,
                    info.range.startColumn,
                    info.range.endLine,
                    info.range.endColumn
                  )
                : undefined,
            }
          },
        })
        disposablesRef.current.push(hoverProvider)
      }
    },
    [language, enableCompletion, enableHover, fetchCompletions, fetchHoverInfo]
  )

  // 监听编辑器内容变化
  useEffect(() => {
    const editor = editorRef.current
    if (!editor || !enableDiagnostics) return

    const disposable = editor.onDidChangeModelContent(() => {
      const model = editor.getModel()
      if (model) {
        debouncedFetchDiagnostics(model.getValue())
      }
    })

    return () => {
      disposable.dispose()
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [editorRef, enableDiagnostics, debouncedFetchDiagnostics])

  // 清理
  useEffect(() => {
    return () => {
      disposablesRef.current.forEach((d) => {
        d.dispose()
      })
      disposablesRef.current = []
    }
  }, [])

  return {
    diagnostics,
    isValidating,
    initializeLSP,
  }
}

// 辅助函数：获取 Monaco 严重性
function getSeverity(
  monaco: typeof Monaco,
  severity: DiagnosticItem['severity']
): Monaco.MarkerSeverity {
  switch (severity) {
    case 'error':
      return monaco.MarkerSeverity.Error
    case 'warning':
      return monaco.MarkerSeverity.Warning
    case 'info':
      return monaco.MarkerSeverity.Info
    case 'hint':
      return monaco.MarkerSeverity.Hint
    default:
      return monaco.MarkerSeverity.Info
  }
}

// 辅助函数：获取补全类型
function getCompletionKind(
  monaco: typeof Monaco,
  kind: string
): Monaco.languages.CompletionItemKind {
  const kindMap: Record<string, Monaco.languages.CompletionItemKind> = {
    function: monaco.languages.CompletionItemKind.Function,
    method: monaco.languages.CompletionItemKind.Method,
    class: monaco.languages.CompletionItemKind.Class,
    variable: monaco.languages.CompletionItemKind.Variable,
    property: monaco.languages.CompletionItemKind.Property,
    module: monaco.languages.CompletionItemKind.Module,
    keyword: monaco.languages.CompletionItemKind.Keyword,
    constant: monaco.languages.CompletionItemKind.Constant,
    snippet: monaco.languages.CompletionItemKind.Snippet,
  }
  return kindMap[kind] || monaco.languages.CompletionItemKind.Text
}
