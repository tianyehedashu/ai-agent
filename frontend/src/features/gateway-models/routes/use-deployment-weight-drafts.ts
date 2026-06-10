import { useCallback, useMemo, useState } from 'react'

import type { GatewayModel } from '@/api/gateway'

/** 待保存的 deployment 权重变更（modelName → 新 weight）。 */
export interface DeploymentWeightChange {
  modelName: string
  weight: number
}

interface DeploymentWeightDrafts {
  /** 行内输入框展示值：草稿优先，未编辑时回退模型持久化 weight */
  weightByName: ReadonlyMap<string, number>
  setWeight: (modelName: string, weight: number) => void
  /** 与持久化值不同的草稿，随「保存」一并提交 */
  changes: readonly DeploymentWeightChange[]
}

/**
 * deployment 权重草稿状态。
 *
 * 权重属于模型（deployment）而非路由实体，但 UI 上要求与「保存路由」
 * 一致的提交时机：编辑只改草稿，保存时由调用方一并提交变更。
 */
export function useDeploymentWeightDrafts(models: readonly GatewayModel[]): DeploymentWeightDrafts {
  const [drafts, setDrafts] = useState<ReadonlyMap<string, number>>(new Map())

  const persistedByName = useMemo(() => new Map(models.map((m) => [m.name, m.weight])), [models])

  const weightByName = useMemo(() => {
    const merged = new Map(persistedByName)
    for (const [name, weight] of drafts) merged.set(name, weight)
    return merged
  }, [persistedByName, drafts])

  const setWeight = useCallback((modelName: string, weight: number): void => {
    setDrafts((prev) => new Map(prev).set(modelName, weight))
  }, [])

  const changes = useMemo(
    () =>
      [...drafts]
        .filter(([name, weight]) => {
          const persisted = persistedByName.get(name)
          return persisted !== undefined && persisted !== weight
        })
        .map(([modelName, weight]) => ({ modelName, weight })),
    [drafts, persistedByName]
  )

  return { weightByName, setWeight, changes }
}
