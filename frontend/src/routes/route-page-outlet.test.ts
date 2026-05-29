import { expect, test } from 'vitest'

import { routePageOutletKey } from '@/routes/route-page-outlet-key'

test('routePageOutletKey keeps /chat stable when session id appears', () => {
  expect(routePageOutletKey('/chat')).toBe('/chat')
  expect(routePageOutletKey('/chat/')).toBe('/chat')
  expect(routePageOutletKey('/chat/7cabf39d-3ffa-4c29-9dc4-f963e4482e6a')).toBe('/chat')
})

test('routePageOutletKey keeps /video-tasks stable for session id', () => {
  expect(routePageOutletKey('/video-tasks')).toBe('/video-tasks')
  expect(routePageOutletKey('/video-tasks/abc')).toBe('/video-tasks')
  expect(routePageOutletKey('/video-tasks/history')).toBe('/video-tasks/history')
})

test('routePageOutletKey remounts on distinct top-level routes', () => {
  expect(routePageOutletKey('/settings')).toBe('/settings')
  expect(routePageOutletKey('/agents')).toBe('/agents')
})
