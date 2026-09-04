import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/input';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar, Field } from '@/components/FilterBar';
import { DataTable, type Column } from '@/components/DataTable';
import { TableSkeleton } from '@/components/ui/skeleton';
import { RunStatus } from '@/components/RunBadges';
import { KpiStrip, ChannelSplit } from '@/components/KpiStrip';
import { Badge, channelTone } from '@/components/ui/badge';
import { api, PAGE_SIZE, type PagedResponse } from '@/lib/api';
import {
  defaultRange, fromDateInput, toDateInput,
} from '@/lib/dates';
import { fmtCompact, fmtMoney } from '@/lib/utils';

type Mode = 'all' | 'marketplace' | 'retail';

type SaleRow = {
  nomenclature_key: string;
  characteristic_key: string | null;
  article: string | null;
  size: string | null;
  channel: string;
  quantity: number;
  amount: number;
  date: string | null;
  type: string;
  warehouse: string | null;
  organization: string | null;
};

const dashOrValue = (v: unknown) =>
  v ? String(v) : <span className="text-text-3">—</span>;

const columns: Column<SaleRow>[] = [
  {
    key: 'date', header: 'Дата', date: true,
    width: '150px',
  },
  {
    key: 'article', header: 'Артикул',
    mono: true, width: '110px',
    format: dashOrValue,
  },
  { key: 'size', header: 'Размер', width: '100px' },
  {
    key: 'channel', header: 'Канал', width: '92px',
    format: (v) => (
      <Badge tone={channelTone(String(v ?? ''))}>
        {String(v ?? '—')}
      </Badge>
    ),
  },
  {
    key: 'type', header: 'Тип', width: '86px',
    format: (v) => (
      <span
        className={
          v === 'возврат' ? 'text-negative' : 'text-text-2'
        }
      >
        {String(v ?? '')}
      </span>
    ),
  },
  {
    key: 'warehouse', header: 'Склад',
    format: dashOrValue,
    className: 'max-w-[220px] truncate',
  },
  {
    key: 'organization', header: 'Организация',
    format: dashOrValue,
    className: 'max-w-[220px] truncate',
  },
  { key: 'quantity', header: 'Кол-во', numeric: true, width: '90px' },
  {
    key: 'amount', header: 'Сумма, сом', numeric: true,
    format: (v) => {
      const n = Number(v ?? 0);
      const cls = n < 0 ? 'text-negative' : 'text-text';
      return <span className={cls}>{fmtMoney(n)}</span>;
    },
  },
];

export function SalesPage() {
  const range = defaultRange(90);
  const [mode, setMode] = useState<Mode>('all');
  const [from, setFrom] = useState(toDateInput(range.from));
  const [to, setTo] = useState(toDateInput(range.to));
  const [channel, setChannel] = useState('');
  const [result, setResult] =
    useState<PagedResponse<SaleRow> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const rows = (result?.records as SaleRow[]) || [];
  const total = result?.total ?? 0;

  const kpis = useMemo(() => {
    if (!rows.length) return null;
    let amount = 0;
    let qty = 0;
    const skus = new Set<string>();
    const returns = { n: 0, amount: 0 };
    const chSplit = new Map<string, number>();
    for (const r of rows) {
      amount += Number(r.amount || 0);
      qty += Number(r.quantity || 0);
      if (r.article) skus.add(r.article);
      if (r.type === 'возврат') {
        returns.n += 1;
        returns.amount += Number(r.amount || 0);
      }
      chSplit.set(
        r.channel || 'unknown',
        (chSplit.get(r.channel || 'unknown') || 0) + 1,
      );
    }
    const chs = Array.from(chSplit.entries())
      .map(([channel, count]) => ({ channel, count }))
      .sort((a, b) => b.count - a.count);
    return { amount, qty, skus: skus.size, returns, chs };
  }, [rows]);

  const run = async (p = 1) => {
    setLoading(true);
    setError(null);
    try {
      const df = fromDateInput(from);
      const dt = fromDateInput(to, true);
      let r: PagedResponse;
      if (mode === 'all') {
        r = await api.allSales(df, dt, p, PAGE_SIZE);
      } else if (mode === 'retail') {
        r = await api.retailSales(df, dt, p, PAGE_SIZE);
      } else {
        r = await api.marketplaceSales(
          df, dt, channel || null, p, PAGE_SIZE,
        );
      }
      setResult(r as PagedResponse<SaleRow>);
      setPage(p);
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void run(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Отчёт"
        title="Продажи"
        description="Данные из «Отчёта комиссионера»
        (маркетплейсы) и «Отчёта о розничных продажах».
        Возвраты учитываются как отрицательные записи."
      />

      <FilterBar>
        <Field label="Источник">
          <Select
            value={mode}
            onChange={(e) => setMode(e.target.value as Mode)}
          >
            <option value="all">Все продажи</option>
            <option value="marketplace">Маркетплейсы</option>
            <option value="retail">Розница</option>
          </Select>
        </Field>
        <Field label="Дата с">
          <Input
            type="date" value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </Field>
        <Field label="Дата по">
          <Input
            type="date" value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </Field>
        <Field label="Канал">
          <Select
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            disabled={mode !== 'marketplace'}
          >
            <option value="">Все каналы</option>
            <option value="WB">WB</option>
            <option value="Ozon">Ozon</option>
            <option value="Lamoda">Lamoda</option>
            <option value="unknown">неопределён</option>
          </Select>
        </Field>
        <div className="ml-auto flex items-end gap-2">
          <Button onClick={() => run(1)} disabled={loading}>
            {loading ? 'Загрузка…' : 'Загрузить'}
          </Button>
        </div>
      </FilterBar>

      <div className="mb-4">
        <RunStatus
          count={total}
          error={error}
          loading={loading}
        />
      </div>

      {kpis && !loading && total <= rows.length && (
        <>
          <KpiStrip
            items={[
              {
                label: 'Оборот',
                value: fmtMoney(kpis.amount),
                hint: kpis.returns.n > 0
                  ? `с учётом ${kpis.returns.n.toLocaleString('ru-RU')} возвратов`
                  : undefined,
                tone: kpis.amount < 0 ? 'negative' : 'default',
              },
              {
                label: 'Записей',
                value: fmtCompact(rows.length),
                hint: 'проведено операций',
              },
              {
                label: 'Артикулов',
                value: fmtCompact(kpis.skus),
                hint: 'уникальных SKU',
              },
              {
                label: 'Кол-во',
                value: fmtCompact(kpis.qty),
                hint: 'единиц товара',
              },
            ]}
          />
          <div className="mb-6 max-w-md">
            <div className="eyebrow mb-2">Каналы</div>
            <ChannelSplit data={kpis.chs} />
          </div>
        </>
      )}

      {loading ? (
        <TableSkeleton />
      ) : (
        <DataTable<SaleRow>
          data={rows}
          columns={columns}
          filename={`sales_${mode}_${from}_${to}.csv`}
          serverPagination={{
            page,
            size: PAGE_SIZE,
            total,
            loading,
            onPageChange: (p) => void run(p),
          }}
        />
      )}
    </div>
  );
}
