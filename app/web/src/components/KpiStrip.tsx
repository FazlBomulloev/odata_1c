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
        'grid gap-4 mb-8 stagger',
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
          className="group relative rounded-xl bg-surface
          border border-border p-5 lift overflow-hidden shine
          cursor-default"
        >
          <div
            className="absolute inset-x-0 top-0 h-px opacity-0
            group-hover:opacity-100 transition-opacity duration-300
            grad-accent"
          />
          <div className="eyebrow mb-3">{it.label}</div>
          <div
            className={cn(
              'font-display text-32 leading-none tracking-tight',
              'font-semibold tabular',
              toneMap[it.tone ?? 'default'],
            )}
          >
            {it.value}
          </div>
          {it.hint && (
            <div className="text-11 text-text-3 mt-2.5 tabular">
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
        bg-surface-2 shadow-inner"
      >
        {data.map((d) => (
          <span
            key={d.channel}
            style={{
              width: `${(d.count / total) * 100}%`,
              background: colorFor(d.channel),
              transition: 'width 400ms ease',
            }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-11">
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
