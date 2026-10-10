import type { ComponentProps } from 'react'
import { Link } from 'react-router-dom'
import './glow-action.css'

function GlowDecoration() {
  return (
    <>
      <span className="glow-action-animations" aria-hidden="true">
        <span className="glow-action-aura" />
        <span className="glow-action-stars-mask">
          <span className="glow-action-stars" />
        </span>
      </span>
      <span className="glow-action-borders-mask" aria-hidden="true">
        <span className="glow-action-borders" />
      </span>
    </>
  )
}

export function GlowLink({ children, className = '', ...props }: ComponentProps<typeof Link>) {
  return (
    <span className="glow-action-wrap">
      <GlowDecoration />
      <Link {...props} className={`button primary glow-action-control ${className}`.trim()}>
        <span className="glow-action-label">{children}</span>
      </Link>
    </span>
  )
}

export function GlowButton({
  children,
  className = '',
  type = 'button',
  ...props
}: ComponentProps<'button'>) {
  return (
    <span className="glow-action-wrap" data-disabled={props.disabled || undefined}>
      <GlowDecoration />
      <button
        {...props}
        type={type}
        className={`button primary glow-action-control ${className}`.trim()}
      >
        <span className="glow-action-label">{children}</span>
      </button>
    </span>
  )
}
