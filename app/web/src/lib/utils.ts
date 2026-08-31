import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const nf0 = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 0,
});
const nf2 = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});

export function fmtNumber(n: number | null | undefined) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return Number.isInteger(n) ? nf0.format(n) : nf2.format(n);
}

export function fmtMoney(n: number | null | undefined) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${nf2.format(n)} ₽`;
}

export function fmtCompact(n: number | null | undefined) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  if (Math.abs(n) >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(2).replace('.', ',')} млн`;
  }
  if (Math.abs(n) >= 10_000) {
    return `${(n / 1_000).toFixed(1).replace('.', ',')} тыс`;
  }
  return nf0.format(n);
}

export function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString('ru-RU', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  }) + ', ' + d.toLocaleTimeString('ru-RU', {
    hour: '2-digit', minute: '2-digit',
  });
}

export function fmtDateShort(iso: string | null | undefined) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString('ru-RU', {
    year: '2-digit', month: '2-digit', day: '2-digit',
  });
}

export function fmtDuration(ms: number | null | undefined) {
  if (ms === null || ms === undefined) return '—';
  if (ms < 1000) return `${ms} мс`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1).replace('.', ',')} с`;
  const m = Math.floor(s / 60);
  const r = Math.round(s - m * 60);
  return `${m} мин ${r} с`;
}
