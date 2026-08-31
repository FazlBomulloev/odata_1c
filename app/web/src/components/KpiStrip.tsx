import { cn } from '@/lib/utils';

export type KpiItem = {
  label: string;
  value: string;
  hint?: string;
  tone?: 'default' | 'positive' | 'negative' | 'muted';
  mono?: boolean;
};

const toneMap: Record<
  NonNullable<KpiItem['tone']>, string
> = {
  default: 'text-ink',
  positive: 'text-positive',
  negative: 'text-negative',
  muted: 'text-ink-3',
};

export function KpiStrip({
  items, className,
}: {
  items: KpiItem[];
  className?: string;
}) {
  if (!items.length) return null;
  return (
    <div
      className={cn(
        'grid gap-px bg-rule border border-rule rounded',
        'overflow-hidden mb-6',
        `grid-cols-2 md:grid-cols-${Math.min(items.length, 4)}`,
        className,
      )}
      style={{
        gridTemplateColumns:
          `repeat(${items.length}, minmax(0, 1fr))`,
      }}
    >
      {items.map((it, i) => (
        <div key={i} className="bg-card px-5 py-4">
          <div className="eyebrow mb-2">{it.label}</div>
          <div
            className={cn(
              'text-28 leading-none tracking-tight',
              it.mono !== false && 'font-mono tabular',
              toneMap[it.tone ?? 'default'],
            )}
          >
            {it.value}
          </div>
          {it.hint && (
            <div className="text-12 text-ink-3 mt-1.5">
              {it.hint}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function ChannelSplit({
  data, className,
}: {
  data: { channel: string; count: number }[];
  className?: string;
}) {
  const total = data.reduce((s, d) => s + d.count, 0);
  if (!total) return null;
  const colorFor = (c: string) => {
    const v = c.toLowerCase();
    if (v === 'wb') return 'var(--wb)';
    if (v === 'ozon') return 'var(--ozon)';
    if (v === 'lamoda') return 'var(--lamoda)';
    if (v === 'магазин') return 'var(--retail)';
    return 'var(--unknown)';
  };
  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex h-1.5 w-full overflow-hidden rounded-sm">
        {data.map((d) => (
          <span
            key={d.channel}
            style={{
              width: `${(d.count / total) * 100}%`,
              background: colorFor(d.channel),
            }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-11">
        {data.map((d) => (
          <span
            key={d.channel}
            className="flex items-center gap-1.5 text-ink-2"
          >
            <span
              className="h-2 w-2 rounded-sm"
              style={{ background: colorFor(d.channel) }}
            />
            {d.channel}{' '}
            <span className="text-ink-3 font-mono tabular">
              {((d.count / total) * 100).toFixed(0)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
