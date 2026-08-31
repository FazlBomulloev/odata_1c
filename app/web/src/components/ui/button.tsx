import * as React from 'react';
import { cn } from '@/lib/utils';

type Variant = 'primary' | 'ghost' | 'quiet' | 'destructive';
type Size = 'sm' | 'md';

const variants: Record<Variant, string> = {
  primary:
    'bg-card text-ink border border-ink ' +
    'hover:bg-ink hover:text-card ' +
    'disabled:!bg-wash disabled:!text-ink-3 ' +
    'disabled:!border-rule-2',
  ghost:
    'bg-card text-ink hover:bg-wash border border-rule',
  quiet:
    'bg-transparent text-ink-2 hover:text-ink hover:bg-wash',
  destructive:
    'bg-transparent text-negative hover:bg-negative-tint',
};

const sizes: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-12',
  md: 'h-9 px-3.5 text-13.5',
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
        'rounded whitespace-nowrap font-medium',
        'transition-colors duration-100',
        'focus-visible:outline-none focus-visible:ring-2',
        'focus-visible:ring-[color:var(--accent)]/40',
        'focus-visible:ring-offset-1 focus-visible:ring-offset-paper',
        'disabled:pointer-events-none disabled:opacity-70',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
});
