import * as React from 'react';
import { cn } from '@/lib/utils';

export function Card({
  className, ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'bg-card border border-rule rounded', className,
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
      className={cn('px-4 py-3 hairline-b', className)}
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
        'text-14 font-medium tracking-tight text-ink', className,
      )}
      {...props}
    />
  );
}

export function CardContent({
  className, ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('px-4 py-3', className)} {...props} />
  );
}
