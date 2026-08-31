import * as React from 'react';
import { cn } from '@/lib/utils';

export type Tone =
  | 'default'
  | 'positive'
  | 'negative'
  | 'warning'
  | 'wb'
  | 'ozon'
  | 'lamoda'
  | 'retail'
  | 'unknown'
  | 'muted';

const tones: Record<Tone, string> = {
  default:
    'bg-[color:var(--accent-tint)] text-[color:var(--accent)]',
  positive:
    'bg-positive-tint text-positive',
  negative:
    'bg-negative-tint text-negative',
  warning:
    'bg-warning-tint text-warning',
  wb:
    'bg-wb-tint text-wb',
  ozon:
    'bg-ozon-tint text-ozon',
  lamoda:
    'bg-lamoda-tint text-lamoda',
  retail:
    'bg-retail-tint text-retail',
  unknown:
    'bg-unknown-tint text-unknown',
  muted:
    'bg-wash text-ink-2',
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
        'inline-flex items-center gap-1 px-1.5 py-0.5',
        'rounded-sm text-11 font-medium tracking-wide',
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
