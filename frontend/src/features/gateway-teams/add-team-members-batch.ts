import { teamsApi } from '@/api/gateway/teams'

export interface AddTeamMemberBatchItem {
  userId: string
  label: string
}

export interface AddTeamMembersBatchResult {
  succeeded: number
  failures: { label: string; message: string }[]
}

export async function addTeamMembersSequentially(
  teamId: string,
  items: readonly AddTeamMemberBatchItem[],
  role: string,
  onProgress?: (completed: number, total: number) => void
): Promise<AddTeamMembersBatchResult> {
  const failures: { label: string; message: string }[] = []
  let succeeded = 0
  const total = items.length

  for (let i = 0; i < items.length; i += 1) {
    const item = items[i]
    try {
      await teamsApi.addMember(teamId, { user_id: item.userId, role })
      succeeded += 1
    } catch (error) {
      failures.push({
        label: item.label,
        message: error instanceof Error ? error.message : '添加失败',
      })
    }
    onProgress?.(i + 1, total)
  }

  return { succeeded, failures }
}
