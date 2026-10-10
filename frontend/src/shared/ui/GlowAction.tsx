import type { ComponentProps } from 'react'
import { Link } from 'react-router-dom'
import './glow-action.css'

function GlowDecoration() {
  return (
    <span className="glow-action-decor" aria-hidden="true">
      <span className="glow-action-aura" />
      <span className="glow-action-stars">
        <span className="glow-action-light" />
      </span>
      <span className="glow-action-ring">
        <span className="glow-action-light" />
      </span>
    </span>
  )
}

export function GlowLink({ children, className = '', ...props }: ComponentProps<typeof Link>) {
  return (
    <Link {...props} className={`button primary glow-action ${className}`.trim()}>
      <GlowDecoration />
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
      <GlowDecoration />
      <span className="glow-action-label">{children}</span>
    </button>
  )
}
