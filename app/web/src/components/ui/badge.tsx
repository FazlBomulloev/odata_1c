import * as React from 'react';
import { cn } from '@/lib/utils';

export type Tone =
  | 'default'
  | 'positive'
  | 'negative'
  | 'warning'
  | 'info'
  | 'wb'
  | 'ozon'
  | 'lamoda'
  | 'retail'
  | 'unknown'
  | 'muted';

const tones: Record<Tone, string> = {
  default:
    'bg-accent-tint text-accent ring-1 ring-inset ring-accent/20',
  positive:
    'bg-positive-tint text-positive ring-1 ring-inset ' +
    'ring-positive/20',
  negative:
    'bg-negative-tint text-negative ring-1 ring-inset ' +
    'ring-negative/20',
  warning:
    'bg-warning-tint text-warning ring-1 ring-inset ' +
    'ring-warning/25',
  info:
    'bg-info-tint text-info ring-1 ring-inset ring-info/20',
  wb:
    'bg-wb-tint text-wb ring-1 ring-inset ring-wb/25',
  ozon:
    'bg-ozon-tint text-ozon ring-1 ring-inset ring-ozon/25',
  lamoda:
    'bg-lamoda-tint text-lamoda ring-1 ring-inset ring-lamoda/25',
  retail:
    'bg-retail-tint text-retail ring-1 ring-inset ring-retail/25',
  unknown:
    'bg-unknown-tint text-unknown ring-1 ring-inset ring-unknown/25',
  muted:
    'bg-surface-2 text-text-2 ring-1 ring-inset ring-border',
};

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({
  className, tone = 'default', ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5',
        'rounded-md text-10 font-semibold tracking-wider uppercase',
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

export function channelTone(channel: string): Tone {
  const c = (channel || '').toLowerCase();
  if (c === 'wb') return 'wb';
  if (c === 'ozon') return 'ozon';
  if (c === 'lamoda') return 'lamoda';
  if (c === 'магазин') return 'retail';
  if (c === 'unknown') return 'unknown';
  return 'muted';
}
