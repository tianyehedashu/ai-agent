import type { PersonalGatewayModel } from '@/api/gateway'

import type { PersonalModelFormValues } from './personal-model-form'

export function personalModelFormValuesFromModel(m: PersonalGatewayModel): PersonalModelFormValues {
  return {
    display_name: m.display_name,
    provider: m.provider,
    model_id: m.model_id,
    credential_id: m.credential_id,
    model_types: m.model_types,
  }
}
