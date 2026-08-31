import * as React from 'react';
import { cn } from '@/lib/utils';

const fieldBase =
  'h-9 w-full rounded-lg bg-surface text-13.5 text-text ' +
  'border border-border px-3 shadow-xs ' +
  'transition-all duration-150 ' +
  'placeholder:text-text-3 ' +
  'hover:border-border-2 ' +
  'focus:outline-none focus:border-accent ' +
  'focus:ring-2 focus:ring-accent/25 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed';

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(fieldBase, className)}
      {...props}
    />
  );
});

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...props }, ref) {
  return (
    <select
      ref={ref}
      className={cn(fieldBase, 'pr-8 appearance-none', className)}
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml;utf8," +
          "<svg xmlns='http://www.w3.org/2000/svg' " +
          "width='10' height='6' viewBox='0 0 10 6'>" +
          "<path d='M1 1l4 4 4-4' stroke='%238B8DA3' " +
          "stroke-width='1.4' fill='none' " +
          "stroke-linecap='round' stroke-linejoin='round'/>" +
          "</svg>\")",
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 10px center',
      }}
      {...props}
    >
      {children}
    </select>
  );
});

export function Label({
  className,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn('eyebrow block mb-1.5', className)}
      {...props}
    />
  );
}
