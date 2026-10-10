import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: ReactNode
  /** React 19 lets a plain function component take `ref` as a normal prop. */
  ref?: Ref<HTMLButtonElement>
}

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-lime text-[#111318] hover:bg-lime-deep shadow-[0_12px_26px_-16px_rgba(199,243,107,0.85)] active:translate-y-px',
  secondary:
    'border border-line bg-raised text-ink hover:border-[#3d434e] hover:bg-[#262b33] active:translate-y-px',
  ghost: 'text-muted hover:bg-white/[0.06] hover:text-ink',
  danger:
    'border border-danger/40 bg-danger/10 text-danger hover:border-danger/60 hover:bg-danger/[0.18] active:translate-y-px',
}

const SIZES: Record<Size, string> = {
  sm: 'h-8 gap-1.5 px-3 text-[12.5px]',
  md: 'h-10 gap-2 px-4 text-[13.5px]',
  lg: 'h-12 gap-2.5 px-5 text-sm',
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  className = '',
  children,
  disabled,
  type = 'button',
  ref,
  ...rest
}: ButtonProps) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={[
        'inline-flex select-none items-center justify-center rounded-lg font-medium',
        'transition-[background-color,border-color,color,transform,box-shadow] duration-150',
        'disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none',
        SIZES[size],
        VARIANTS[variant],
        className,
      ].join(' ')}
      {...rest}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : icon ? (
        <span className="shrink-0 [&>svg]:h-4 [&>svg]:w-4" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {children}
    </button>
  )
}
