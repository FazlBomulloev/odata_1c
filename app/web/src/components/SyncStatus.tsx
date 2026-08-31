import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api, type SyncStatusResponse } from '@/lib/api';
import { cn } from '@/lib/utils';

export function SyncStatus() {
  const [data, setData] = useState<SyncStatusResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [, setTick] = useState(0);

  const load = useCallback(async () => {
    try {
      setData(await api.syncStatus());
    } catch {
      setData(null);
    }
  }, []);

  useEffect(() => {
    load();
    const t = window.setInterval(load, 60_000);
    const c = window.setInterval(() => setTick((n) => n + 1), 30_000);
    return () => {
      window.clearInterval(t);
      window.clearInterval(c);
    };
  }, [load]);

  const onRefresh = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api.syncRefresh(false);
      window.setTimeout(load, 1500);
    } catch {
      // статус подтянется на следующем тике
    } finally {
      setBusy(false);
    }
  };

  const info = summarize(data);

  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          'flex items-center gap-2 text-11 tabular',
          info.tone === 'ok' && 'text-text-2',
          info.tone === 'warn' && 'text-warning',
          info.tone === 'bad' && 'text-negative',
        )}
        title={info.title}
      >
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            info.tone === 'ok' && 'bg-positive dot-breathe',
            info.tone === 'warn' && 'bg-warning dot-breathe',
            info.tone === 'bad' && 'bg-negative',
          )}
        />
        {info.label}
      </span>
      <button
        onClick={onRefresh}
        disabled={busy || info.anyRunning}
        className={cn(
          'h-7 w-7 flex items-center justify-center rounded-md',
          'text-text-3 hover:text-text hover:bg-surface',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'transition-colors',
        )}
        title="Запустить синхронизацию сейчас"
      >
        <RefreshCw
          className={cn(
            'h-3.5 w-3.5',
            (busy || info.anyRunning) && 'animate-spin',
          )}
          strokeWidth={2}
        />
      </button>
    </div>
  );
}

type Info = {
  label: string;
  title: string;
  tone: 'ok' | 'warn' | 'bad';
  anyRunning: boolean;
};

function summarize(data: SyncStatusResponse | null): Info {
  if (!data || data.runs.length === 0) {
    return {
      label: 'нет данных',
      title: 'Синхронизация ещё не запускалась',
      tone: 'warn',
      anyRunning: false,
    };
  }

  const anyRunning = data.runs.some((r) => r.status === 'running');
  const anyError = data.runs.some((r) => r.status === 'error');

  const finished = data.runs
    .map((r) => (r.finished_at ? new Date(r.finished_at) : null))
    .filter((d): d is Date => d !== null)
    .sort((a, b) => a.getTime() - b.getTime());

  const oldest = finished[0] ?? null;
  const now = Date.now();

  const kindsLine = data.runs
    .map(
      (r) =>
        `${r.kind}: ${r.status}` +
        (r.record_count !== null ? ` (${r.record_count})` : '') +
        (r.error ? ` — ${r.error}` : ''),
    )
    .join('\n');

  const title = `Интервал: ${data.interval_hours} ч\n` + kindsLine;

  if (anyRunning) {
    return {
      label: 'обновление…',
      title,
      tone: 'warn',
      anyRunning: true,
    };
  }
  if (!oldest) {
    return {
      label: 'нет успешных прогонов',
      title,
      tone: 'bad',
      anyRunning,
    };
  }

  const ageMs = now - oldest.getTime();
  const label = fmtAgo(ageMs);
  const staleAfter = data.interval_hours * 3600 * 1000 * 2;
  const tone: Info['tone'] = anyError
    ? 'bad'
    : ageMs > staleAfter
      ? 'warn'
      : 'ok';
  return { label, title, tone, anyRunning };
}

function fmtAgo(ms: number): string {
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}с назад`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} мин назад`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} ч назад`;
  const day = Math.floor(hr / 24);
  return `${day} дн назад`;
}
