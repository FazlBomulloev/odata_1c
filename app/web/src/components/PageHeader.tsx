import { cn } from '@/lib/utils';

export function PageHeader({
  eyebrow, title, description, actions, className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex items-end justify-between gap-6 mb-6', className,
      )}
    >
      <div className="min-w-0">
        {eyebrow && (
          <div className="eyebrow mb-1.5">{eyebrow}</div>
        )}
        <h1 className="text-22 font-medium tracking-tight text-ink">
          {title}
        </h1>
        {description && (
          <p className="text-13 text-ink-3 mt-1 max-w-2xl">
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
  );
}
