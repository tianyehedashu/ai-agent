import { expect, test } from 'vitest'

import {
  isVideoTaskToolName,
  parseVideoTaskOutput,
  VIDEO_TASK_TOOL_NAMES,
} from './tool-block-utils'

test('parseVideoTaskOutput returns taskId when output is valid JSON with task_id', () => {
  expect(parseVideoTaskOutput(JSON.stringify({ task_id: 'tid-123' }))).toEqual({
    taskId: 'tid-123',
  })
  expect(
    parseVideoTaskOutput(
      JSON.stringify({
        task_id: 'tid-456',
        workflow_id: 'wf',
        status: 'running',
      })
    )
  ).toEqual({ taskId: 'tid-456' })
})

test('parseVideoTaskOutput returns null for invalid or missing task_id', () => {
  expect(parseVideoTaskOutput('')).toBeNull()
  expect(parseVideoTaskOutput('not json')).toBeNull()
  expect(parseVideoTaskOutput('{}')).toBeNull()
  expect(parseVideoTaskOutput(JSON.stringify({ workflow_id: 'w' }))).toBeNull()
  expect(parseVideoTaskOutput(JSON.stringify({ task_id: null }))).toBeNull()
})

test('isVideoTaskToolName identifies video tools', () => {
  expect(isVideoTaskToolName('amazon_video_submit')).toBe(true)
  expect(isVideoTaskToolName('amazon_video_poll')).toBe(true)
  expect(isVideoTaskToolName('read_file')).toBe(false)
  expect(isVideoTaskToolName('')).toBe(false)
})

test('VIDEO_TASK_TOOL_NAMES contains expected names', () => {
  expect(VIDEO_TASK_TOOL_NAMES).toContain('amazon_video_submit')
  expect(VIDEO_TASK_TOOL_NAMES).toContain('amazon_video_poll')
})
