import { useEffect, useMemo, useState } from 'react';
import {
  Search, Plus, Trash2, Pencil, ImageOff, RefreshCw,
} from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { KpiStrip } from '@/components/KpiStrip';
import { TableSkeleton } from '@/components/ui/skeleton';
import { ProductForm } from '@/components/ProductForm';
import { api, type ProductListItem } from '@/lib/api';
import { fmtCompact } from '@/lib/utils';

type FormState =
  | { open: false }
  | { open: true; mode: 'create' }
  | { open: true; mode: 'edit'; row: ProductListItem };

export function ProductsPage() {
  const [rows, setRows] = useState<ProductListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prefix, setPrefix] = useState('');
  const [articleSearch, setArticleSearch] = useState('');
  const [onlyActive, setOnlyActive] = useState(true);
  const [form, setForm] = useState<FormState>({ open: false });
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.productsList({
        prefix,
        limit: 500,
        only_active: onlyActive,
      });
      setRows(r);
    } catch (e) {
      setError((e as Error).message);
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    if (!articleSearch) return rows;
    const s = articleSearch.toLowerCase();
    return rows.filter(
      (r) =>
        r.article.toLowerCase().includes(s) ||
        r.name.toLowerCase().includes(s),
    );
  }, [rows, articleSearch]);

  const kpis = useMemo(() => {
    const total = rows.length;
    const withPhoto = rows.filter((r) => r.photo_key).length;
    const active = rows.filter((r) => !r.deletion_mark).length;
    return { total, withPhoto, active };
  }, [rows]);

  const onDelete = async (article: string) => {
    if (!confirm(`Пометить "${article}" на удаление?`)) return;
    setDeleting(article);
    try {
      await api.productDelete(article);
      await load();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Каталог"
        title="Товары"
        description="Номенклатура из 1С. Создание, обновление,
        мягкое удаление. Свободный артикул подбирается автоматически
        по префиксу."
        actions={
          <>
            <Button variant="ghost" onClick={() => void load()}>
              <RefreshCw className="h-3.5 w-3.5" />
              Обновить
            </Button>
            <Button
              onClick={() => setForm({ open: true, mode: 'create' })}
            >
              <Plus className="h-3.5 w-3.5" />
              Новый товар
            </Button>
          </>
        }
      />

      <div
        className="flex flex-wrap items-end gap-3 p-4 mb-6
        rounded-xl bg-surface border border-border shadow-sm"
      >
        <div className="flex flex-col min-w-[200px]">
          <span className="eyebrow mb-1.5">Префикс артикула</span>
          <div className="flex gap-2">
            <Input
              value={prefix}
              onChange={(e) => setPrefix(e.target.value)}
              placeholder="например 180"
              className="font-mono w-[180px]"
              onKeyDown={(e) => {
                if (e.key === 'Enter') void load();
              }}
            />
            <Button variant="ghost" onClick={() => void load()}>
              загрузить
            </Button>
          </div>
        </div>

        <div className="flex flex-col min-w-[260px] flex-1">
          <span className="eyebrow mb-1.5">Поиск по загруженным</span>
          <div className="relative">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2
              h-3.5 w-3.5 text-text-3"
            />
            <Input
              value={articleSearch}
              onChange={(e) => setArticleSearch(e.target.value)}
              placeholder="артикул или название"
              className="pl-9"
            />
          </div>
        </div>

        <div className="flex flex-col">
          <span className="eyebrow mb-1.5">Только активные</span>
          <label className="flex items-center gap-2 h-9">
            <input
              type="checkbox"
              checked={onlyActive}
              onChange={(e) => setOnlyActive(e.target.checked)}
              className="h-4 w-4 rounded border-rule
              accent-[color:var(--accent)]"
            />
            <span className="text-13 text-text-2">
              скрыть помеченные
            </span>
          </label>
        </div>
      </div>

      {error && (
        <div
          className="text-13 text-negative bg-negative-tint
          rounded-lg px-4 py-3 mb-4"
        >
          {error}
        </div>
      )}

      {!loading && rows.length > 0 && (
        <KpiStrip
          items={[
            { label: 'Всего', value: fmtCompact(kpis.total) },
            {
              label: 'Активных',
              value: fmtCompact(kpis.active),
              hint: 'без пометки на удаление',
            },
            {
              label: 'С фото',
              value: fmtCompact(kpis.withPhoto),
              hint: 'основная картинка задана',
            },
          ]}
        />
      )}

      {loading ? (
        <TableSkeleton />
      ) : (
        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns:
              'repeat(auto-fill, minmax(220px, 1fr))',
          }}
        >
          {filtered.map((r) => (
            <ProductCard
              key={r.ref_key}
              row={r}
              onEdit={() =>
                setForm({ open: true, mode: 'edit', row: r })
              }
              onDelete={() => void onDelete(r.article)}
              deleting={deleting === r.article}
            />
          ))}
          {!filtered.length && (
            <div
              className="col-span-full text-13 text-text-3 py-16
              text-center rounded-xl bg-surface border border-border"
            >
              Ничего не найдено
            </div>
          )}
        </div>
      )}

      {form.open && (
        <ProductForm
          mode={form.mode}
          initial={
            form.mode === 'edit'
              ? {
                  article: form.row.article,
                  name: form.row.name,
                  price: String(form.row.price || ''),
                }
              : undefined
          }
          onClose={() => setForm({ open: false })}
          onSaved={async () => {
            setForm({ open: false });
            await load();
          }}
        />
      )}
    </div>
  );
}

function ProductCard({
  row,
  onEdit,
  onDelete,
  deleting,
}: {
  row: ProductListItem;
  onEdit: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const hasPhoto = !!row.photo_key && !imgFailed;
  const src = row.photo_key
    ? api.productPhotoUrl(row.photo_key)
    : '';

  return (
    <div
      className="group relative overflow-hidden rounded-xl
      bg-surface border border-border shadow-sm hover:shadow-md
      transition-shadow flex flex-col"
    >
      <div
        className="aspect-square bg-surface-2 flex items-center
        justify-center overflow-hidden relative"
      >
        {hasPhoto ? (
          <img
            src={src}
            alt={row.name}
            className="w-full h-full object-cover"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <ImageOff className="h-8 w-8 text-text-3/50" />
        )}
        {row.deletion_mark && (
          <span
            className="absolute top-2 left-2 text-10 uppercase
            tracking-wider px-2 py-0.5 rounded-md bg-negative/90
            text-white"
          >
            удалён
          </span>
        )}
      </div>
      <div className="p-3 flex-1 flex flex-col">
        <div
          className="font-mono text-11 text-text-3 tracking-wide"
        >
          {row.article}
        </div>
        <div
          className="text-13 text-text font-medium mt-0.5
          line-clamp-2"
          title={row.full_name || row.name}
        >
          {row.name || '—'}
        </div>
        {(row.category_name || row.color) && (
          <div
            className="mt-1 flex flex-wrap gap-1 text-10
            text-text-3"
          >
            {row.category_name && (
              <span
                className="px-1.5 py-0.5 rounded bg-surface-2
                border border-border"
              >
                {row.category_name}
              </span>
            )}
            {row.color && (
              <span
                className="px-1.5 py-0.5 rounded bg-surface-2
                border border-border"
              >
                {row.color}
              </span>
            )}
          </div>
        )}
        {row.sizes && row.sizes.length > 0 && (
          <div
            className="mt-1.5 flex flex-wrap gap-1"
            title={`${row.sizes.length} размер(ов)`}
          >
            {row.sizes.slice(0, 8).map((s, i) => (
              <span
                key={`${s.global}-${s.ru}-${i}`}
                className="text-10 font-mono px-1.5 py-0.5
                rounded bg-accent-tint text-text tabular"
              >
                {s.ru || s.global}
              </span>
            ))}
            {row.sizes.length > 8 && (
              <span
                className="text-10 text-text-3 px-1.5 py-0.5"
              >
                +{row.sizes.length - 8}
              </span>
            )}
          </div>
        )}
        <div className="mt-auto pt-2 flex items-center justify-between">
          <div className="text-13 font-mono tabular text-text">
            {row.price
              ? row.price.toLocaleString('ru-RU')
              : '—'}
          </div>
          <div
            className="flex items-center gap-1 opacity-0
            group-hover:opacity-100 transition-opacity"
          >
            <button
              onClick={onEdit}
              title="Редактировать"
              className="h-7 w-7 rounded-md text-text-3 hover:text-text
              hover:bg-surface-2 flex items-center justify-center"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={onDelete}
              disabled={deleting}
              title="Удалить"
              className="h-7 w-7 rounded-md text-text-3
              hover:text-negative hover:bg-negative-tint
              flex items-center justify-center disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
