import * as React from 'react';
import { cn } from '@/lib/utils';

export function Card({
  className, ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'bg-surface border border-border rounded-lg shadow-sm',
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className, ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('px-5 py-3.5 hairline-b', className)}
      {...props}
    />
  );
}

export function CardTitle({
  className, ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <h3
      className={cn(
        'text-14 font-medium tracking-tight text-text',
        className,
      )}
      {...props}
    />
  );
}

export function CardContent({
  className, ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('px-5 py-4', className)} {...props} />
  );
}
