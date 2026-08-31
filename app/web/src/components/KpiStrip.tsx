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
  default: 'text-text',
  positive: 'text-positive',
  negative: 'text-negative',
  muted: 'text-text-3',
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
        'grid gap-3 mb-6',
        className,
      )}
      style={{
        gridTemplateColumns:
          `repeat(${items.length}, minmax(0, 1fr))`,
      }}
    >
      {items.map((it, i) => (
        <div
          key={i}
          className="relative rounded-lg bg-surface border border-border
          px-5 py-4 surface-hover shadow-sm"
        >
          <div className="eyebrow mb-2.5">{it.label}</div>
          <div
            className={cn(
              'font-display text-28 leading-none tracking-tight',
              'font-medium tabular',
              toneMap[it.tone ?? 'default'],
            )}
          >
            {it.value}
          </div>
          {it.hint && (
            <div className="text-11 text-text-3 mt-2 tabular">
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
    <div className={cn('space-y-2.5', className)}>
      <div
        className="flex h-2 w-full overflow-hidden rounded-full
        bg-surface-2"
      >
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
            className="flex items-center gap-1.5 text-text-2"
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: colorFor(d.channel) }}
            />
            {d.channel}{' '}
            <span className="text-text-3 tabular">
              {((d.count / total) * 100).toFixed(0)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
