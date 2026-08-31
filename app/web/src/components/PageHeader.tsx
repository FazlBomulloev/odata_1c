import { cn } from '@/lib/utils';

export function PageHeader({
  eyebrow, title, description, actions, className, hero,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  hero?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn('mb-8', className)}
    >
      <div className="flex items-end justify-between gap-6">
        <div className="min-w-0">
          {eyebrow && (
            <div className="eyebrow mb-2">{eyebrow}</div>
          )}
          <h1
            className="font-display text-32 font-semibold
            tracking-tight text-text leading-none"
          >
            {title}
          </h1>
          {description && (
            <p className="text-13 text-text-3 mt-2.5 max-w-2xl">
              {description}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex items-center gap-2 shrink-0">
            {actions}
          </div>
        )}
      </div>
      {hero && (
        <div className="mt-6">
          {hero}
        </div>
      )}
    </div>
  );
}

export function HeroMetric({
  label, value, delta, hint, tone = 'default',
}: {
  label: string;
  value: string;
  delta?: string;
  hint?: string;
  tone?: 'default' | 'positive' | 'negative';
}) {
  const deltaTone =
    tone === 'positive'
      ? 'text-positive bg-positive-tint ring-positive/20'
      : tone === 'negative'
        ? 'text-negative bg-negative-tint ring-negative/20'
        : 'text-text-2 bg-surface-2 ring-border';

  return (
    <div
      className="relative overflow-hidden rounded-xl bg-surface
      border border-border shadow-sm px-8 py-6"
    >
      <div
        className="absolute -top-24 -right-16 h-48 w-48 rounded-full
        bg-accent/5 blur-3xl pointer-events-none"
      />
      <div className="eyebrow mb-3">{label}</div>
      <div className="flex items-end gap-4">
        <div
          className="font-display text-56 font-medium text-text
          tabular leading-none"
        >
          {value}
        </div>
        {delta && (
          <span
            className={cn(
              'inline-flex items-center rounded-md px-2 py-1',
              'text-12 font-medium tabular ring-1 ring-inset mb-2',
              deltaTone,
            )}
          >
            {delta}
          </span>
        )}
      </div>
      {hint && (
        <div className="text-12 text-text-3 mt-3">{hint}</div>
      )}
    </div>
  );
}
