import * as React from 'react';
import { cn } from '@/lib/utils';

type Variant = 'primary' | 'ghost' | 'quiet' | 'destructive';
type Size = 'sm' | 'md';

const variants: Record<Variant, string> = {
  primary:
    'grad-accent text-white ' +
    'shadow-[0_2px_8px_-2px_rgba(8,145,178,0.35)] ' +
    'hover:shadow-[0_6px_16px_-4px_rgba(8,145,178,0.5)] ' +
    'hover:-translate-y-px ' +
    'disabled:!bg-none disabled:!bg-surface-2 ' +
    'disabled:!text-text-3 disabled:!shadow-none',
  ghost:
    'bg-surface text-text border border-border ' +
    'hover:border-border-2 hover:bg-surface-2 ' +
    'shadow-xs hover:shadow-sm',
  quiet:
    'bg-transparent text-text-2 hover:text-text ' +
    'hover:bg-surface-2',
  destructive:
    'bg-transparent text-negative hover:bg-negative-tint ' +
    'border border-transparent hover:border-negative/25',
};

const sizes: Record<Size, string> = {
  sm: 'h-7 px-3 text-12',
  md: 'h-9 px-4 text-13 font-medium',
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
        'rounded-lg whitespace-nowrap font-medium',
        'transition-all duration-200',
        'focus-visible:outline-none focus-visible:ring-2',
        'focus-visible:ring-accent/40 focus-visible:ring-offset-2',
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
