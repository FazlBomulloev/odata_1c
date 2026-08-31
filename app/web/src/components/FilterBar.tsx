import { cn } from '@/lib/utils';

export function FilterBar({
  className, children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-end gap-3 p-4 mb-6',
        'rounded-xl bg-surface border border-border shadow-sm',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Field({
  label, children, className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col min-w-[140px]', className)}>
      <span className="eyebrow mb-1.5">{label}</span>
      {children}
    </div>
  );
}
