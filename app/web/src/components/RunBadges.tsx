import { Badge } from '@/components/ui/badge';
import { AlertCircle } from 'lucide-react';
import { fmtDuration } from '@/lib/utils';

export function RunStatus({
  count, ms, error, loading,
}: {
  count?: number | null;
  ms?: number | null;
  error?: string | null;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-12 text-text-3">
        <span className="inline-block h-1.5 w-1.5 rounded-full
        bg-accent dot-breathe" />
        Загрузка из 1С…
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex items-start gap-2 text-12 text-negative">
        <AlertCircle className="h-3.5 w-3.5 mt-px shrink-0" />
        <span className="max-w-lg truncate" title={error}>
          Ошибка · {error.slice(0, 200)}
        </span>
      </div>
    );
  }
  if (typeof count !== 'number') return null;
  return (
    <div className="flex items-center gap-3 text-12 text-text-3">
      <span>
        <span className="font-mono tabular text-text">
          {count.toLocaleString('ru-RU')}
        </span>{' '}
        записей
      </span>
      <span className="text-border-2">·</span>
      <span>
        за{' '}
        <span className="font-mono tabular text-text-2">
          {fmtDuration(ms ?? 0)}
        </span>
      </span>
      {typeof ms === 'number' && ms < 500 && (
        <Badge tone="muted">из кэша</Badge>
      )}
    </div>
  );
}
