import type { ComponentProps } from 'react'
import { Link } from 'react-router-dom'

export function GlowLink({ children, className = '', ...props }: ComponentProps<typeof Link>) {
  return (
    <Link {...props} className={`button primary glow-action ${className}`.trim()}>
      <span className="glow-action-label">{children}</span>
    </Link>
  )
}

export function GlowButton({
  children,
  className = '',
  type = 'button',
  ...props
}: ComponentProps<'button'>) {
  return (
    <button {...props} type={type} className={`button primary glow-action ${className}`.trim()}>
      <span className="glow-action-label">{children}</span>
    </button>
  )
}
