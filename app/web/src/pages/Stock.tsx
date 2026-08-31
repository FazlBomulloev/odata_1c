import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/input';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar, Field } from '@/components/FilterBar';
import { DataTable, type Column } from '@/components/DataTable';
import { TableSkeleton } from '@/components/ui/skeleton';
import { RunStatus } from '@/components/RunBadges';
import { KpiStrip } from '@/components/KpiStrip';
import { api, type CatalogItem, type RunResult } from '@/lib/api';
import { fmtCompact } from '@/lib/utils';

type StockRow = {
  name: string;
  article: string;
  barcode: string;
  size: string;
  warehouse: string;
  organization: string;
  quantity: number;
};

const columns: Column<StockRow>[] = [
  { key: 'article', header: 'Артикул', mono: true, width: '110px' },
  {
    key: 'name', header: 'Наименование',
    className: 'min-w-[280px] max-w-[440px] truncate',
  },
  { key: 'size', header: 'Размер', width: '100px' },
  { key: 'warehouse', header: 'Склад' },
  { key: 'organization', header: 'Организация' },
  { key: 'quantity', header: 'Остаток', numeric: true },
  {
    key: 'barcode', header: 'Штрихкод',
    mono: true, className: 'text-ink-3',
  },
];

type Mode = 'filter' | 'article';

export function StockPage() {
  const [mode, setMode] = useState<Mode>('filter');
  const [warehouse, setWarehouse] = useState('');
  const [organization, setOrganization] = useState('');
  const [onlyPositive, setOnlyPositive] = useState(true);
  const [article, setArticle] = useState('');
  const [warehouses, setWarehouses] = useState<CatalogItem[]>([]);
  const [orgs, setOrgs] = useState<CatalogItem[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.warehouses().then(setWarehouses).catch(() => {});
    api.organizations().then(setOrgs).catch(() => {});
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows = (result?.records as StockRow[]) || [];

  const kpis = useMemo(() => {
    if (!rows.length) return null;
    let total = 0;
    const whs = new Set<string>();
    const skus = new Set<string>();
    for (const r of rows) {
      total += Number(r.quantity || 0);
      if (r.warehouse) whs.add(r.warehouse);
      if (r.article) skus.add(r.article);
    }
    return { total, whs: whs.size, skus: skus.size };
  }, [rows]);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      let r: RunResult;
      if (mode === 'article') {
        r = await api.stockByArticle(article);
      } else {
        r = await api.stock({
          warehouse, organization,
          only_positive: onlyPositive,
        });
      }
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
        title="Остатки"
        description="Текущие складские остатки. Компоненты
        количества суммируются автоматически."
      />

      <FilterBar>
        <Field label="Режим">
          <Select
            value={mode}
            onChange={(e) => setMode(e.target.value as Mode)}
          >
            <option value="filter">По фильтру</option>
            <option value="article">По артикулу</option>
          </Select>
        </Field>
        {mode === 'filter' ? (
          <>
            <Field label="Организация" className="min-w-[200px]">
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
            <Field label="Склад" className="min-w-[200px]">
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
            <Field label="Только положительные">
              <label className="flex items-center gap-2 h-9">
                <input
                  type="checkbox"
                  checked={onlyPositive}
                  onChange={(e) => setOnlyPositive(e.target.checked)}
                  className="h-4 w-4 rounded border-rule
                  accent-[color:var(--accent)]"
                />
                <span className="text-13 text-ink-2">
                  скрыть нулевые
                </span>
              </label>
            </Field>
          </>
        ) : (
          <Field label="Артикул" className="min-w-[240px]">
            <Input
              value={article}
              placeholder="например 18057"
              onChange={(e) => setArticle(e.target.value)}
              className="font-mono"
            />
          </Field>
        )}
        <div className="ml-auto flex items-end">
          <Button
            onClick={run}
            disabled={
              loading || (mode === 'article' && !article.trim())
            }
          >
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
            { label: 'Позиций', value: fmtCompact(rows.length) },
            {
              label: 'Единиц',
              value: fmtCompact(kpis.total),
              hint: 'суммарно на складах',
            },
            {
              label: 'Артикулов',
              value: fmtCompact(kpis.skus),
              hint: 'уникальных SKU',
            },
            {
              label: 'Складов',
              value: fmtCompact(kpis.whs),
              hint: 'с остатками',
            },
          ]}
        />
      )}

      {loading ? (
        <TableSkeleton />
      ) : (
        <DataTable<StockRow>
          data={rows}
          columns={columns}
          filename={`stock_${mode}.csv`}
        />
      )}
    </div>
  );
}
