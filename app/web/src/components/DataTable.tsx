import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Download, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn, fmtNumber, fmtDate } from '@/lib/utils';
import { downloadCSV } from '@/lib/csv';

export type Column<T> = {
  key: keyof T & string;
  header: string;
  className?: string;
  headerClass?: string;
  format?: (value: unknown, row: T) => React.ReactNode;
  numeric?: boolean;
  mono?: boolean;
  date?: boolean;
  width?: string;
};

export type ServerPagination = {
  page: number;
  size: number;
  total: number;
  loading?: boolean;
  onPageChange: (page: number) => void;
};

type Props<T extends Record<string, unknown>> = {
  data: T[];
  columns: Column<T>[];
  filename?: string;
  searchable?: boolean;
  pageSize?: number;
  emptyMessage?: string;
  serverPagination?: ServerPagination;
};

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  filename = 'export.csv',
  searchable = true,
  pageSize = 50,
  emptyMessage = 'Ничего не нашлось за выбранный период',
  serverPagination,
}: Props<T>) {
  const [sort, setSort] = useState<{
    key: string; dir: 'asc' | 'desc';
  } | null>(null);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const isServer = !!serverPagination;

  const filtered = useMemo(() => {
    if (!query.trim()) return data;
    const q = query.trim().toLowerCase();
    return data.filter((row) =>
      columns.some((c) => {
        const v = row[c.key];
        return String(v ?? '').toLowerCase().includes(q);
      }),
    );
  }, [data, columns, query]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const { key, dir } = sort;
    const s = [...filtered].sort((a, b) => {
      const av = a[key] as unknown;
      const bv = b[key] as unknown;
      if (av === bv) return 0;
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === 'number' && typeof bv === 'number') {
        return dir === 'asc' ? av - bv : bv - av;
      }
      return dir === 'asc'
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return s;
  }, [filtered, sort]);

  const totalPages = isServer
    ? Math.max(
        1,
        Math.ceil(
          serverPagination!.total / serverPagination!.size,
        ),
      )
    : Math.max(1, Math.ceil(sorted.length / pageSize));
  const pageSafe = isServer
    ? Math.min(serverPagination!.page, totalPages)
    : Math.min(page, totalPages);
  const rows = isServer
    ? sorted
    : sorted.slice(
        (pageSafe - 1) * pageSize, pageSafe * pageSize,
      );
  const goPage = (p: number) => {
    if (isServer) {
      serverPagination!.onPageChange(p);
    } else {
      setPage(p);
    }
  };

  const toggleSort = (key: string) => {
    setSort((s) => {
      if (!s || s.key !== key) return { key, dir: 'asc' };
      if (s.dir === 'asc') return { key, dir: 'desc' };
      return null;
    });
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {searchable && (
          <div className="relative w-72">
            <Search
              className="absolute left-3 top-2.5 h-3.5 w-3.5
              text-text-3 pointer-events-none"
              strokeWidth={2}
            />
            <Input
              placeholder="Найти в таблице"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              className="pl-9 h-9 text-13"
            />
          </div>
        )}
        <span className="text-11 text-text-3 font-mono tabular">
          {isServer
            ? serverPagination!.total.toLocaleString('ru-RU')
            : sorted.length.toLocaleString('ru-RU')}
          {!isServer && query && data.length !== sorted.length &&
            ` / ${data.length.toLocaleString('ru-RU')}`}
          {' записей'}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => downloadCSV(sorted, filename)}
            disabled={sorted.length === 0}
          >
            <Download className="h-3.5 w-3.5" strokeWidth={2} />
            Экспорт CSV
          </Button>
        </div>
      </div>

      <div
        className="rounded-xl overflow-hidden bg-surface
        border border-border shadow-sm"
      >
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-13">
            <thead>
              <tr className="border-b border-border">
                {columns.map((c) => {
                  const isSorted = sort?.key === c.key;
                  const Icon =
                    sort?.dir === 'desc' ? ArrowDown : ArrowUp;
                  return (
                    <th
                      key={c.key}
                      className={cn(
                        'text-left eyebrow font-semibold',
                        'px-4 py-3.5 whitespace-nowrap select-none',
                        'cursor-pointer hover:text-text',
                        'bg-bg-2/60 backdrop-blur',
                        'transition-colors duration-150',
                        c.numeric && 'text-right',
                        isSorted && '!text-accent',
                        c.headerClass,
                      )}
                      onClick={() => toggleSort(c.key)}
                      style={c.width ? { width: c.width } : undefined}
                    >
                      <span className={cn(
                        'inline-flex items-center gap-1',
                        c.numeric && 'justify-end w-full',
                      )}>
                        {c.header}
                        {isSorted && (
                          <Icon className="h-2.5 w-2.5" />
                        )}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={i}
                  className={cn(
                    i > 0 && 'border-t border-border/60',
                    'hover:bg-accent-tint/50 transition-colors',
                    'duration-100',
                  )}
                >
                  {columns.map((c) => {
                    const raw = row[c.key];
                    let content: React.ReactNode;
                    if (c.format) {
                      content = c.format(raw, row);
                    } else if (c.date) {
                      content = fmtDate(raw as string);
                    } else if (c.numeric) {
                      content = fmtNumber(raw as number);
                    } else if (raw === null || raw === undefined) {
                      content = (
                        <span className="text-text-3">—</span>
                      );
                    } else {
                      content = String(raw);
                    }
                    return (
                      <td
                        key={c.key}
                        className={cn(
                          'px-4 py-3 whitespace-nowrap text-text',
                          c.mono && 'font-mono tabular',
                          c.numeric && 'text-right font-mono tabular',
                          c.date && 'text-text-2',
                          c.className,
                        )}
                      >
                        {content}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="text-center text-text-3 py-16 text-13"
                  >
                    {emptyMessage}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div
          className="flex items-center justify-between mt-4
          text-11 text-text-3"
        >
          <span>
            Страница{' '}
            <span className="font-mono tabular text-text-2">
              {pageSafe}
            </span>{' '}
            из{' '}
            <span className="font-mono tabular text-text-2">
              {totalPages}
            </span>
          </span>
          <div className="flex gap-1">
            <Button
              variant="ghost" size="sm"
              onClick={() => goPage(1)}
              disabled={pageSafe <= 1 || serverPagination?.loading}
            >«</Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => goPage(Math.max(1, pageSafe - 1))}
              disabled={pageSafe <= 1 || serverPagination?.loading}
            >‹</Button>
            <Button
              variant="ghost" size="sm"
              onClick={() =>
                goPage(Math.min(totalPages, pageSafe + 1))
              }
              disabled={
                pageSafe >= totalPages || serverPagination?.loading
              }
            >›</Button>
            <Button
              variant="ghost" size="sm"
              onClick={() => goPage(totalPages)}
              disabled={
                pageSafe >= totalPages || serverPagination?.loading
              }
            >»</Button>
          </div>
        </div>
      )}
    </div>
  );
}
