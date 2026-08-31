import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/input';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar, Field } from '@/components/FilterBar';
import { DataTable, type Column } from '@/components/DataTable';
import { TableSkeleton } from '@/components/ui/skeleton';
import { RunStatus } from '@/components/RunBadges';
import { KpiStrip } from '@/components/KpiStrip';
import { Badge } from '@/components/ui/badge';
import { api, type CatalogItem, type RunResult } from '@/lib/api';
import {
  defaultRange, fromDateInput, toDateInput,
} from '@/lib/dates';
import { fmtCompact } from '@/lib/utils';

type MoveRow = {
  period: string | null;
  name: string;
  article: string;
  size: string;
  quantity: number;
  operation_type: string;
  warehouse_from: string;
  warehouse_to: string;
  organization_from: string;
  organization_to: string;
  document_kind: string;
  document_number: string;
  document_date: string | null;
};

const opTone = (op: string) => {
  if (op === 'перемещение') return 'default';
  if (op === 'межфирменное') return 'default';
  if (op === 'списание') return 'negative';
  if (op === 'приход' || op === 'оприходование') return 'positive';
  return 'muted';
};

const columns: Column<MoveRow>[] = [
  { key: 'period', header: 'Период', date: true, width: '160px' },
  {
    key: 'operation_type', header: 'Операция', width: '140px',
    format: (v) => (
      <Badge tone={opTone(String(v ?? ''))}>
        {String(v ?? '')}
      </Badge>
    ),
  },
  {
    key: 'article', header: 'Артикул', mono: true, width: '110px',
    format: (v) => v
      ? String(v)
      : <span className="text-ink-3">—</span>,
  },
  {
    key: 'name', header: 'Наименование',
    className: 'min-w-[280px] max-w-[420px] truncate',
  },
  { key: 'size', header: 'Размер', width: '100px' },
  { key: 'quantity', header: 'Кол-во', numeric: true },
  { key: 'warehouse_from', header: 'Со склада' },
  { key: 'warehouse_to', header: 'На склад' },
  {
    key: 'document_number', header: '№ док.',
    mono: true, width: '120px',
  },
];

const KINDS = [
  { value: 'all', label: 'Все' },
  { value: 'transfers', label: 'Перемещения' },
  { value: 'receipts', label: 'Приход' },
  { value: 'expenses', label: 'Расход' },
  { value: 'write_offs', label: 'Списания' },
];

export function MovementsPage() {
  const range = defaultRange(7);
  const [from, setFrom] = useState(toDateInput(range.from));
  const [to, setTo] = useState(toDateInput(range.to));
  const [kind, setKind] = useState('all');
  const [organization, setOrganization] = useState('');
  const [warehouse, setWarehouse] = useState('');
  const [warehouses, setWarehouses] = useState<CatalogItem[]>([]);
  const [orgs, setOrgs] = useState<CatalogItem[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.warehouses().then(setWarehouses).catch(() => {});
    api.organizations().then(setOrgs).catch(() => {});
  }, []);

  const rows = (result?.records as MoveRow[]) || [];

  const kpis = useMemo(() => {
    if (!rows.length) return null;
    let qty = 0;
    const skus = new Set<string>();
    const byOp = new Map<string, number>();
    for (const r of rows) {
      qty += Number(r.quantity || 0);
      if (r.article) skus.add(r.article);
      byOp.set(
        r.operation_type,
        (byOp.get(r.operation_type) || 0) + 1,
      );
    }
    const dominant = [...byOp.entries()]
      .sort((a, b) => b[1] - a[1])[0];
    return {
      qty, skus: skus.size,
      dominant: dominant ? dominant[0] : '—',
      dominantCount: dominant ? dominant[1] : 0,
    };
  }, [rows]);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.movements({
        date_from: fromDateInput(from),
        date_to: fromDateInput(to, true),
        kind,
        organization,
        warehouse,
      });
      setResult(r);
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Отчёт"
        title="Движения запасов"
        description="Перемещения, приход, расход и списания. Пары
        Expense/Receipt перемещений собираются в одну запись."
      />

      <FilterBar>
        <Field label="Вид">
          <Select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
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
        <Field label="Организация" className="min-w-[180px]">
          <Select
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
          >
            <option value="">Все</option>
            {orgs.map((o) => (
              <option key={o.ref} value={o.ref}>
                {o.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Склад" className="min-w-[180px]">
          <Select
            value={warehouse}
            onChange={(e) => setWarehouse(e.target.value)}
          >
            <option value="">Все</option>
            {warehouses.map((w) => (
              <option key={w.ref} value={w.ref}>
                {w.name}
              </option>
            ))}
          </Select>
        </Field>
        <div className="ml-auto flex items-end">
          <Button onClick={run} disabled={loading}>
            {loading ? 'Загрузка…' : 'Загрузить'}
          </Button>
        </div>
      </FilterBar>

      <div className="mb-4">
        <RunStatus
          count={result?.record_count}
          ms={result?.duration_ms}
          error={error}
          loading={loading}
        />
      </div>

      {kpis && !loading && (
        <KpiStrip
          items={[
            {
              label: 'Строк движения',
              value: fmtCompact(rows.length),
            },
            {
              label: 'Артикулов',
              value: fmtCompact(kpis.skus),
              hint: 'уникальных SKU',
            },
            {
              label: 'Единиц товара',
              value: fmtCompact(kpis.qty),
            },
            {
              label: 'Основная операция',
              value: kpis.dominant,
              hint: `${kpis.dominantCount.toLocaleString('ru-RU')} строк`,
              mono: false,
            },
          ]}
        />
      )}

      {loading ? (
        <TableSkeleton />
      ) : (
        <DataTable<MoveRow>
          data={rows}
          columns={columns}
          filename={`movements_${kind}_${from}_${to}.csv`}
        />
      )}
    </div>
  );
}
