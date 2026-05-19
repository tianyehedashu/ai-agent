import type React from 'react'

import { Button } from '@/components/ui/button'
import { useUserPreferenceStore } from '@/stores/user-preference'
import type { DisplayCurrency } from '@/types/money'

export function CurrencyToggle(): React.JSX.Element {
  const currency = useUserPreferenceStore((s) => s.displayCurrency)
  const setCurrency = useUserPreferenceStore((s) => s.setDisplayCurrency)

  const toggle = (): void => {
    const next: DisplayCurrency = currency === 'CNY' ? 'USD' : 'CNY'
    setCurrency(next)
  }

  return (
    <Button type="button" variant="outline" size="sm" onClick={toggle} aria-label="切换展示币种">
      {currency === 'CNY' ? '¥ CNY' : '$ USD'}
    </Button>
  )
}
