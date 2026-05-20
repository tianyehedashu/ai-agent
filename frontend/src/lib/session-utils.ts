import type { Session } from '@/types'

/**
 * 按日期将会话分组：今天 / 昨天 / 过去7天 / 更早
 */
export function groupSessionsByDate(sessions: Session[]): Record<string, Session[]> {
  const groups: Record<string, Session[]> = {
    今天: [],
    昨天: [],
    过去7天: [],
    更早: [],
  }

  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const lastWeek = new Date(today)
  lastWeek.setDate(lastWeek.getDate() - 7)

  sessions.forEach((session) => {
    const date = new Date(session.updatedAt)
    if (date >= today) {
      groups['今天'].push(session)
    } else if (date >= yesterday) {
      groups['昨天'].push(session)
    } else if (date >= lastWeek) {
      groups['过去7天'].push(session)
    } else {
      groups['更早'].push(session)
    }
  })

  return groups
}
