import { useEffect, useState } from 'react';
import { RefreshCw, Trash2, Eye, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { PageHeader } from '@/components/PageHeader';
import { DataTable, type Column } from '@/components/DataTable';
import { TableSkeleton } from '@/components/ui/skeleton';
import {
  api, type RunDetail, type RunSummary,
} from '@/lib/api';
import { fmtDate, fmtDuration } from '@/lib/utils';

export function HistoryPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setRuns(await api.runs(200));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const open = async (id: number) => {
    setDetail(await api.run(id));
  };

  const remove = async (id: number) => {
    await api.deleteRun(id);
    setRuns((rs) => rs.filter((r) => r.id !== id));
    if (detail?.id === id) setDetail(null);
  };

  const columns: Column<
    RunSummary & Record<string, unknown>
  >[] = [
    {
      key: 'id', header: '#', mono: true, width: '54px',
    },
    { key: 'method', header: 'Метод', mono: true },
    {
      key: 'status', header: 'Статус', width: '96px',
      format: (v) => {
        const tone =
          v === 'ok' ? 'positive'
          : v === 'error' ? 'negative'
          : 'warning';
        const label =
          v === 'ok' ? 'готово'
          : v === 'error' ? 'ошибка'
          : 'выполняется';
        return <Badge tone={tone}>{label}</Badge>;
      },
    },
    {
      key: 'started_at', header: 'Старт',
      format: (v) => (
        <span className="text-ink-2">
          {fmtDate(v as string)}
        </span>
      ),
    },
    {
      key: 'duration_ms', header: 'Время', numeric: true,
      format: (v) => (
        <span className="font-mono tabular text-ink-2">
          {fmtDuration(v as number)}
        </span>
      ),
    },
    {
      key: 'record_count', header: 'Записей', numeric: true,
    },
    {
      key: 'params', header: 'Параметры',
      className: 'text-11 text-ink-3 font-mono tabular max-w-md truncate',
      format: (v) => JSON.stringify(v),
    },
    {
      key: 'id', header: '', width: '80px',
      format: (_v, row) => (
        <div className="flex gap-0.5 justify-end">
          <Button
            size="sm" variant="quiet"
            onClick={() => open(row.id)}
            title="Открыть"
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="sm" variant="quiet"
            onClick={() => remove(row.id)}
            title="Удалить"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Журнал"
        title="История запусков"
        description="Все запросы к 1С. Результат каждого прогона
        сохранён в SQLite — открывается мгновенно, без повторного
        похода в 1С."
        actions={
          <Button variant="ghost" onClick={load}>
            <RefreshCw className="h-3.5 w-3.5" /> Обновить
          </Button>
        }
      />

      {loading ? (
        <TableSkeleton />
      ) : (
        <DataTable
          data={runs as unknown as Record<string, unknown>[]}
          columns={columns as unknown as Column<
            Record<string, unknown>
          >[]}
          filename="runs.csv"
          searchable={false}
        />
      )}

      {detail && (
        <div className="mt-6 border border-rule rounded bg-card">
          <div className="hairline-b px-4 py-3 flex items-start justify-between">
            <div>
              <div className="eyebrow mb-1">Запуск #{detail.id}</div>
              <div className="text-14 font-medium font-mono">
                {detail.method}
              </div>
              <div className="text-11 text-ink-3 mt-1 font-mono truncate max-w-3xl">
                {JSON.stringify(detail.params)}
              </div>
            </div>
            <Button
              size="sm" variant="quiet"
              onClick={() => setDetail(null)}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          <div className="px-4 py-3">
            <pre className="text-11 font-mono text-ink-2 max-h-[420px]
            overflow-auto scrollbar-thin whitespace-pre-wrap">
              {detail.payload
                ? JSON.stringify(detail.payload.slice(0, 50), null, 2)
                : '— пусто —'}
            </pre>
            {detail.payload && detail.payload.length > 50 && (
              <div className="text-11 text-ink-3 mt-2">
                показаны первые 50 записей из{' '}
                <span className="font-mono tabular">
                  {detail.payload.length}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
