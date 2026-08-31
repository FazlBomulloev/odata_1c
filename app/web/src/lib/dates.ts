export function isoDay(d: Date, endOfDay = false): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const time = endOfDay ? '23:59:59' : '00:00:00';
  return `${yyyy}-${mm}-${dd}T${time}`;
}

export function daysAgo(n: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d;
}

export function todayISO(endOfDay = false): string {
  return isoDay(new Date(), endOfDay);
}

export function defaultRange(days = 30): {
  from: string; to: string;
} {
  return {
    from: isoDay(daysAgo(days)),
    to: isoDay(new Date(), true),
  };
}

export function toDateInput(iso: string): string {
  return iso.slice(0, 10);
}

export function fromDateInput(
  s: string, endOfDay = false,
): string {
  if (!s) return '';
  return `${s}T${endOfDay ? '23:59:59' : '00:00:00'}`;
}
