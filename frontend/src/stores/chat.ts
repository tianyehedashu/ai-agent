import { create } from 'zustand'

import type { Message, Session } from '@/types'

interface ChatState {
  // Current session
  currentSession: Session | null
  setCurrentSession: (session: Session | null) => void

  // Messages
  messages: Message[]
  addMessage: (message: Message) => void
  updateMessage: (id: string, updates: Partial<Message>) => void
  clearMessages: () => void

  // Loading state
  isLoading: boolean
  setIsLoading: (loading: boolean) => void

  // Streaming
  streamingContent: string
  setStreamingContent: (content: string) => void
  appendStreamingContent: (content: string) => void

  // Input
  input: string
  setInput: (input: string) => void
}

export const useChatStore = create<ChatState>((set) => ({
  // Current session
  currentSession: null,
  setCurrentSession: (session) => {
    set({ currentSession: session })
  },

  // Messages
  messages: [],
  addMessage: (message) => {
    set((state) => ({ messages: [...state.messages, message] }))
  },
  updateMessage: (id, updates) => {
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? { ...m, ...updates } : m)),
    }))
  },
  clearMessages: () => {
    set({ messages: [] })
  },

  // Loading state
  isLoading: false,
  setIsLoading: (loading) => {
    set({ isLoading: loading })
  },

  // Streaming
  streamingContent: '',
  setStreamingContent: (content) => {
    set({ streamingContent: content })
  },
  appendStreamingContent: (content) => {
    set((state) => ({ streamingContent: state.streamingContent + content }))
  },

  // Input
  input: '',
  setInput: (input) => {
    set({ input })
  },
}))
