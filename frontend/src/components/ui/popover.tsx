import * as React from 'react'

import * as PopoverPrimitive from '@radix-ui/react-popover'

import { useOverlayPortalReady } from '@/lib/ui-overlay/overlay-portal-ready'
import { deferReleaseUiOverlayLock } from '@/lib/ui-overlay/release-overlay-lock'
import { cn } from '@/lib/utils'

const Popover = (
  props: React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Root>
): React.JSX.Element => (
  <PopoverPrimitive.Root
    {...props}
    modal={props.modal ?? false}
    onOpenChange={(open) => {
      props.onOpenChange?.(open)
      if (!open) {
        deferReleaseUiOverlayLock()
      }
    }}
  />
)

const PopoverTrigger = PopoverPrimitive.Trigger

const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, align = 'center', sideOffset = 4, onCloseAutoFocus, ...props }, ref) => {
  const { container } = useOverlayPortalReady()

  return (
    <PopoverPrimitive.Portal container={container}>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-[80] w-72 rounded-md border bg-popover p-4 text-popover-foreground shadow-md outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
          className
        )}
        onCloseAutoFocus={(e) => {
          e.preventDefault()
          onCloseAutoFocus?.(e)
        }}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
})
PopoverContent.displayName = PopoverPrimitive.Content.displayName

export { Popover, PopoverTrigger, PopoverContent }
