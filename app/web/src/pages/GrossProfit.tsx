import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/input';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar, Field } from '@/components/FilterBar';
import { DataTable, type Column } from '@/components/DataTable';
import { TableSkeleton } from '@/components/ui/skeleton';
import { api, type CatalogItem } from '@/lib/api';
import {
  defaultRange, fromDateInput, toDateInput,
} from '@/lib/dates';
import { fmtMoney, fmtNumber } from '@/lib/utils';

type GroupKey =
  | 'article' | 'size' | 'warehouse'
  | 'organization' | 'contractor' | 'month';

type Row = {
  article?: string;
  size?: string;
  warehouse?: string;
  organization?: string;
  contractor?: string;
  month?: string;
  quantity: number;
  revenue: number;
  revenue_no_vat: number;
  cost: number;
  cost_no_vat: number;
  gross_profit: number;
  profitability: number;
  unit_cost: number;
};

const GROUP_OPTIONS: { key: GroupKey; label: string }[] = [
  { key: 'article', label: 'Артикул' },
  { key: 'size', label: 'Размер' },
  { key: 'warehouse', label: 'Склад' },
  { key: 'organization', label: 'Организация' },
  { key: 'contractor', label: 'Контрагент' },
  { key: 'month', label: 'Месяц' },
];

export function GrossProfitPage() {
  const range = defaultRange(150);
  const [from, setFrom] = useState(toDateInput(range.from));
  const [to, setTo] = useState(toDateInput(range.to));
  const [article, setArticle] = useState('');
  const [warehouse, setWarehouse] = useState('');
  const [organization, setOrganization] = useState('');
  const [groupBy, setGroupBy] = useState<GroupKey[]>([
    'article', 'size',
  ]);

  const [warehouses, setWarehouses] = useState<CatalogItem[]>([]);
  const [orgs, setOrgs] = useState<CatalogItem[]>([]);
  const [data, setData] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snapshotAt, setSnapshotAt] = useState<string | null>(null);

  useEffect(() => {
    api.warehouses().then(setWarehouses).catch(() => setWarehouses([]));
    api.organizations().then(setOrgs).catch(() => setOrgs([]));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.grossProfit({
        date_from: fromDateInput(from),
        date_to: fromDateInput(to, true),
        article: article.trim() || null,
        warehouse,
        organization,
        group_by: groupBy,
      });
      // /api/gross-profit возвращает cached-формат:
      // { records, snapshot_at, ... }
      const raw = r as unknown as {
        records: Row[];
        snapshot_at: string | null;
      };
      setData(raw.records || []);
      setSnapshotAt(raw.snapshot_at ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setData([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totals = useMemo(() => {
    return data.reduce(
      (acc, r) => {
        acc.quantity += r.quantity;
        acc.revenue += r.revenue;
        acc.cost += r.cost;
        acc.gross += r.gross_profit;
        return acc;
      },
      { quantity: 0, revenue: 0, cost: 0, gross: 0 },
    );
  }, [data]);

  const totalProfitability =
    totals.revenue > 0 ? totals.gross / totals.revenue * 100 : 0;

  const columns = useMemo<Column<Row>[]>(() => {
    const cols: Column<Row>[] = [];
    if (groupBy.includes('article')) {
      cols.push({
        key: 'article', header: 'Артикул',
        mono: true, width: '120px',
        format: (v) => (v ? String(v) : '—'),
      });
    }
    if (groupBy.includes('size')) {
      cols.push({
        key: 'size', header: 'Размер', width: '110px',
        format: (v) => (v ? String(v) : '—'),
      });
    }
    if (groupBy.includes('warehouse')) {
      cols.push({
        key: 'warehouse', header: 'Склад',
        format: (v) => (v ? String(v) : '—'),
      });
    }
    if (groupBy.includes('organization')) {
      cols.push({
        key: 'organization', header: 'Организация',
        format: (v) => (v ? String(v) : '—'),
      });
    }
    if (groupBy.includes('contractor')) {
      cols.push({
        key: 'contractor', header: 'Контрагент',
        format: (v) => (v ? String(v) : '—'),
      });
    }
    if (groupBy.includes('month')) {
      cols.push({
        key: 'month', header: 'Месяц', width: '110px',
        format: (v) => {
          if (!v) return '—';
          const d = new Date(String(v));
          return d.toLocaleDateString('ru-RU', {
            year: 'numeric', month: 'long',
          });
        },
      });
    }
    cols.push(
      { key: 'quantity', header: 'Кол-во', numeric: true, width: '90px' },
      {
        key: 'revenue', header: 'Выручка ₽', numeric: true,
        format: (v) => fmtMoney(Number(v ?? 0)),
      },
      {
        key: 'cost', header: 'Себестоимость ₽', numeric: true,
        format: (v) => {
          const n = Number(v ?? 0);
          const cls = n < 0 ? 'text-negative' : 'text-ink';
          return <span className={cls}>{fmtMoney(n)}</span>;
        },
      },
      {
        key: 'gross_profit', header: 'Прибыль ₽', numeric: true,
        format: (v) => {
          const n = Number(v ?? 0);
          const cls = n < 0 ? 'text-negative' : 'text-positive';
          return <span className={cls}>{fmtMoney(n)}</span>;
        },
      },
      {
        key: 'profitability', header: 'Рент. %', numeric: true,
        width: '90px',
        format: (v) => {
          const n = Number(v ?? 0);
          return `${n.toFixed(2).replace('.', ',')} %`;
        },
      },
      {
        key: 'unit_cost', header: 'С/с ед. ₽', numeric: true,
        format: (v) => fmtMoney(Number(v ?? 0)),
      },
    );
    return cols;
  }, [groupBy]);

  function toggleGroup(k: GroupKey) {
    setGroupBy((cur) =>
      cur.includes(k)
        ? cur.filter((x) => x !== k)
        : [...cur, k],
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Отчёт из регистра «Продажи»"
        title="Валовая прибыль"
        description={
          'Строки — по размеру. Группировку можно менять — таблица '
          + 'агрегируется на лету.'
        }
        actions={
          snapshotAt && (
            <span className="text-11 text-ink-3">
              данные на{' '}
              {new Date(snapshotAt).toLocaleString('ru-RU')}
            </span>
          )
        }
      />

      <FilterBar>
        <Field label="С даты">
          <Input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </Field>
        <Field label="По дату">
          <Input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </Field>
        <Field label="Артикул">
          <Input
            placeholder="напр. 184165"
            value={article}
            onChange={(e) => setArticle(e.target.value)}
            className="min-w-[140px]"
          />
        </Field>
        <Field label="Склад">
          <Select
            value={warehouse}
            onChange={(e) => setWarehouse(e.target.value)}
          >
            <option value="">— все —</option>
            {warehouses.map((w) => (
              <option key={w.ref} value={w.ref}>{w.name}</option>
            ))}
          </Select>
        </Field>
        <Field label="Организация">
          <Select
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
          >
            <option value="">— все —</option>
            {orgs.map((o) => (
              <option key={o.ref} value={o.ref}>{o.name}</option>
            ))}
          </Select>
        </Field>
        <div className="ml-auto flex items-end">
          <Button onClick={() => void load()} disabled={loading}>
            {loading ? 'Загрузка…' : 'Сформировать'}
          </Button>
        </div>
      </FilterBar>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="eyebrow mr-1">Группировка:</span>
        {GROUP_OPTIONS.map((o) => {
          const active = groupBy.includes(o.key);
          return (
            <button
              key={o.key}
              onClick={() => toggleGroup(o.key)}
              className={
                'text-11 px-2 h-6 rounded border '
                + 'transition-colors '
                + (active
                  ? 'border-[color:var(--accent)] text-ink '
                    + 'bg-[color:var(--accent)]/10'
                  : 'border-rule text-ink-3 '
                    + 'hover:text-ink hover:bg-wash')
              }
            >
              {o.label}
            </button>
          );
        })}
      </div>

      <div
        className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5"
      >
        <Kpi label="Количество" value={fmtNumber(totals.quantity)} />
        <Kpi label="Выручка" value={fmtMoney(totals.revenue)} />
        <Kpi
          label="Себестоимость" value={fmtMoney(totals.cost)}
        />
        <Kpi
          label="Прибыль"
          value={fmtMoney(totals.gross)}
          hint={`${totalProfitability.toFixed(2).replace('.', ',')} %`}
        />
      </div>

      {error && (
        <div className="mb-4 text-12 text-negative">{error}</div>
      )}

      {loading ? (
        <TableSkeleton rows={12} />
      ) : (
        <DataTable
          data={data as unknown as Record<string, unknown>[]}
          columns={columns as unknown as Column<
            Record<string, unknown>
          >[]}
          filename="gross-profit.csv"
          emptyMessage="Нет данных за выбранный период"
        />
      )}
    </div>
  );
}

function Kpi({
  label, value, hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="hairline rounded-md bg-card p-4">
      <div className="eyebrow mb-1">{label}</div>
      <div className="text-16 font-mono tabular text-ink">
        {value}
      </div>
      {hint && (
        <div className="text-11 text-ink-3 mt-1">{hint}</div>
      )}
    </div>
  );
}
