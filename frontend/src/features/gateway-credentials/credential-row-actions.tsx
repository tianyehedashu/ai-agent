import type React from 'react'

import { Link } from 'react-router-dom'

import type { ProviderCredential } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import type { CredentialsListTab } from '@/features/gateway-models/paths'
import {
  credentialDetailAddModelsHref,
  credentialDetailHref,
} from '@/features/gateway-models/paths'
import { Trash2 } from '@/lib/lucide-icons'

export interface CredentialRowActionsProps {
  credential: ProviderCredential
  detailTeamId: string
  listTab?: CredentialsListTab
  linkable: boolean
  editable: boolean
  deletePending?: boolean
  onEdit?: (credential: ProviderCredential) => void
  onAddModels?: (credential: ProviderCredential) => void
  onDelete?: (credential: ProviderCredential) => void
}

export function CredentialRowActions({
  credential,
  detailTeamId,
  listTab,
  linkable,
  editable,
  deletePending = false,
  onEdit,
  onAddModels,
  onDelete,
}: CredentialRowActionsProps): React.JSX.Element | null {
  const showDetail = linkable || onEdit !== undefined
  const showModels = editable && (onAddModels !== undefined || linkable)
  const showDelete = editable && onDelete !== undefined

  if (!showDetail && !showModels && !showDelete) return null

  const linkState = listTab ? { credentialsTab: listTab } : undefined

  return (
    <div className="flex items-center gap-0.5">
      {linkable ? (
        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
          <Link
            to={credentialDetailHref(detailTeamId, credential.id, { tab: listTab })}
            state={linkState}
          >
            详情
          </Link>
        </Button>
      ) : onEdit ? (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => {
            onEdit(credential)
          }}
        >
          详情
        </Button>
      ) : null}
      {onAddModels ? (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={() => {
            onAddModels(credential)
          }}
        >
          模型
        </Button>
      ) : editable ? (
        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
          <Link to={credentialDetailAddModelsHref(detailTeamId, credential.id)} state={linkState}>
            模型
          </Link>
        </Button>
      ) : null}
      {showDelete ? (
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 text-destructive hover:text-destructive"
          disabled={deletePending}
          onClick={() => {
            onDelete(credential)
          }}
          aria-label="删除凭据"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      ) : null}
    </div>
  )
}
