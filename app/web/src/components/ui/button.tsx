import * as React from 'react';
import { cn } from '@/lib/utils';

type Variant = 'primary' | 'ghost' | 'quiet' | 'destructive';
type Size = 'sm' | 'md';

const variants: Record<Variant, string> = {
  primary:
    'bg-accent text-accent-fg border border-accent ' +
    'hover:bg-accent-hover hover:border-accent-hover ' +
    'font-medium ' +
    'disabled:!bg-surface-2 disabled:!text-text-3 ' +
    'disabled:!border-border',
  ghost:
    'bg-surface text-text border border-border ' +
    'hover:bg-surface-2 hover:border-border-2',
  quiet:
    'bg-transparent text-text-2 hover:text-text ' +
    'hover:bg-surface-2',
  destructive:
    'bg-transparent text-negative hover:bg-negative-tint ' +
    'border border-transparent hover:border-negative/30',
};

const sizes: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-12',
  md: 'h-9 px-4 text-13',
};

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = React.forwardRef<
  HTMLButtonElement, ButtonProps
>(function Button(
  {
    className, variant = 'primary', size = 'md', ...props
  },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center gap-1.5',
        'rounded-md whitespace-nowrap',
        'transition-all duration-150',
        'focus-visible:outline-none focus-visible:ring-2',
        'focus-visible:ring-accent/50 focus-visible:ring-offset-2',
        'focus-visible:ring-offset-bg',
        'disabled:pointer-events-none disabled:opacity-70',
        'active:scale-[0.98]',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
});
