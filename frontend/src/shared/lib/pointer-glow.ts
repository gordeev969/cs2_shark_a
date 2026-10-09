import { useCallback, type PointerEvent } from 'react'

/** Delegates a decorative effect without rendering React on every pointer move. */
export function usePointerGlow(selector: string) {
  return useCallback(
    (event: PointerEvent<HTMLElement>) => {
      if (event.pointerType !== 'mouse' || !(event.target instanceof Element)) return
      const card = event.target.closest<HTMLElement>(selector)
      if (!card || !event.currentTarget.contains(card)) return
      const bounds = card.getBoundingClientRect()
      card.style.setProperty('--pointer-x', `${event.clientX - bounds.left}px`)
      card.style.setProperty('--pointer-y', `${event.clientY - bounds.top}px`)
    },
    [selector],
  )
}
