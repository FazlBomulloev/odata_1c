import { useCallback, useEffect, useState } from 'react';
import { api, type SyncStatusResponse } from '@/lib/api';
import { cn } from '@/lib/utils';

/**
 * Плашка «данные обновлены N назад» + кнопка обновления.
 * Показывает самое старое finished_at из всех kinds — то есть
 * «худшую» свежесть по любому из синков.
 */
export function SyncStatus() {
  const [data, setData] = useState<SyncStatusResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);

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
      // ignore — статус подтянется на следующем интервале
    } finally {
      setBusy(false);
    }
  };

  const info = summarize(data, tick);

  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          'flex items-center gap-1.5 text-11',
          info.tone === 'ok' && 'text-ink-3',
          info.tone === 'warn' && 'text-ink-2',
          info.tone === 'bad' && 'text-negative',
        )}
        title={info.title}
      >
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            info.tone === 'ok' && 'bg-positive',
            info.tone === 'warn' && 'bg-yellow-500',
            info.tone === 'bad' && 'bg-negative',
          )}
        />
        {info.label}
      </span>
      <button
        onClick={onRefresh}
        disabled={busy || info.anyRunning}
        className={cn(
          'text-11 px-2 h-6 rounded border border-rule',
          'text-ink-2 hover:text-ink hover:bg-wash',
          'disabled:opacity-60 disabled:cursor-not-allowed',
          'transition-colors',
        )}
        title="Запустить фоновую синхронизацию"
      >
        {busy || info.anyRunning ? 'синк…' : 'обновить'}
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

function summarize(
  data: SyncStatusResponse | null,
  _tick: number,
): Info {
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

  const title =
    `Интервал: ${data.interval_hours} ч\n` + kindsLine;

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
  const label = 'обновлено ' + fmtAgo(ageMs);
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
  if (sec < 60) return `${sec} с назад`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} мин назад`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} ч назад`;
  const day = Math.floor(hr / 24);
  return `${day} дн назад`;
}
