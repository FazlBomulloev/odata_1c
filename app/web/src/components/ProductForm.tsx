import { useEffect, useState } from 'react';
import { X, Plus, Trash2, Sparkles, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input, Select, Label } from '@/components/ui/input';
import {
  api, ApiError,
  type ProductSizePayload,
} from '@/lib/api';

export type FormMode = 'create' | 'edit';

type Size = ProductSizePayload;

type Values = {
  article: string;
  articlePrefix: string;
  name: string;
  description: string;
  price: string;
  category: string;
  color: string;
  group: string;
  sizes: Size[];
  photos: string[];
};

const emptyValues: Values = {
  article: '',
  articlePrefix: '',
  name: '',
  description: '',
  price: '',
  category: '',
  color: '',
  group: '',
  sizes: [],
  photos: [],
};

export function ProductForm({
  mode,
  initial,
  onClose,
  onSaved,
}: {
  mode: FormMode;
  initial?: Partial<Values> & { article?: string };
  onClose: () => void;
  onSaved: (article: string) => void;
}) {
  const [v, setV] = useState<Values>({
    ...emptyValues,
    ...initial,
  });
  const [articleStatus, setArticleStatus] = useState<
    'idle' | 'checking' | 'free' | 'taken'
  >('idle');
  const [pickingArticle, setPickingArticle] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof Values>(k: K, val: Values[K]) =>
    setV((s) => ({ ...s, [k]: val }));

  const setSize = (i: number, patch: Partial<Size>) =>
    setV((s) => ({
      ...s,
      sizes: s.sizes.map((row, idx) =>
        idx === i ? { ...row, ...patch } : row,
      ),
    }));

  const addSize = () =>
    setV((s) => ({
      ...s,
      sizes: [...s.sizes, { global: '', ru: '', barcode: '' }],
    }));

  const removeSize = (i: number) =>
    setV((s) => ({
      ...s,
      sizes: s.sizes.filter((_, idx) => idx !== i),
    }));

  const addPhoto = () =>
    setV((s) => ({ ...s, photos: [...s.photos, ''] }));

  const setPhoto = (i: number, url: string) =>
    setV((s) => ({
      ...s,
      photos: s.photos.map((u, idx) => (idx === i ? url : u)),
    }));

  const removePhoto = (i: number) =>
    setV((s) => ({
      ...s,
      photos: s.photos.filter((_, idx) => idx !== i),
    }));

  useEffect(() => {
    if (mode !== 'create' || !v.article) {
      setArticleStatus('idle');
      return;
    }
    setArticleStatus('checking');
    const h = window.setTimeout(async () => {
      try {
        const r = await api.productExists(v.article);
        setArticleStatus(r.exists ? 'taken' : 'free');
      } catch {
        setArticleStatus('idle');
      }
    }, 350);
    return () => window.clearTimeout(h);
  }, [v.article, mode]);

  const pickNextArticle = async () => {
    if (!v.articlePrefix) return;
    setPickingArticle(true);
    try {
      const r = await api.productNextArticle(v.articlePrefix);
      set('article', r.article);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPickingArticle(false);
    }
  };

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const cleanSizes = v.sizes.filter(
        (s) => s.global && s.ru && s.barcode,
      );
      const cleanPhotos = v.photos
        .map((u) => u.trim())
        .filter(Boolean);

      if (mode === 'create') {
        const usePrefix = !v.article && !!v.articlePrefix;
        const r = await api.productCreate({
          article: v.article || null,
          article_prefix: usePrefix ? v.articlePrefix : null,
          name: v.name,
          description: v.description,
          price: Number(v.price),
          category: v.category,
          color: v.color,
          group: v.group,
          sizes: cleanSizes,
          photos: cleanPhotos,
        });
        onSaved(r.article);
      } else if (initial?.article) {
        const patch: {
          name?: string;
          price?: number;
          sizes?: Size[];
        } = {};
        if (v.name) patch.name = v.name;
        if (v.price) patch.price = Number(v.price);
        if (cleanSizes.length) patch.sizes = cleanSizes;
        await api.productUpdate(initial.article, patch);
        onSaved(initial.article);
      }
    } catch (e) {
      const err = e as ApiError | Error;
      setError(err.message || 'Ошибка сохранения');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal onClose={onClose} title={
      mode === 'create' ? 'Новый товар' : 'Редактировать товар'
    }>
      <div className="grid gap-5">
        {mode === 'create' && (
          <div className="grid grid-cols-[1fr_auto_1fr] gap-3 items-end">
            <div>
              <Label>Префикс артикула</Label>
              <Input
                value={v.articlePrefix}
                onChange={(e) =>
                  set('articlePrefix', e.target.value)
                }
                placeholder="например 180"
              />
            </div>
            <Button
              variant="ghost"
              size="md"
              onClick={pickNextArticle}
              disabled={!v.articlePrefix || pickingArticle}
              className="mb-0"
            >
              <Sparkles className="h-3.5 w-3.5" />
              {pickingArticle ? '…' : 'Свободный'}
            </Button>
            <div>
              <Label>Артикул</Label>
              <div className="relative">
                <Input
                  value={v.article}
                  onChange={(e) => set('article', e.target.value)}
                  placeholder="или впишите вручную"
                  className={
                    'font-mono ' +
                    (articleStatus === 'taken'
                      ? '!border-negative !ring-negative/25'
                      : articleStatus === 'free'
                        ? '!border-positive !ring-positive/25'
                        : '')
                  }
                />
                {articleStatus !== 'idle' && v.article && (
                  <ArticleBadge status={articleStatus} />
                )}
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Название</Label>
            <Input
              value={v.name}
              onChange={(e) => set('name', e.target.value)}
              placeholder="Куртка мужская"
            />
          </div>
          <div>
            <Label>Цена</Label>
            <Input
              type="number"
              inputMode="decimal"
              value={v.price}
              onChange={(e) => set('price', e.target.value)}
              placeholder="0"
              className="font-mono"
            />
          </div>
        </div>

        {mode === 'create' && (
          <>
            <div>
              <Label>Описание</Label>
              <textarea
                value={v.description}
                onChange={(e) => set('description', e.target.value)}
                rows={2}
                className="w-full rounded-lg bg-surface text-13.5
                text-text border border-border px-3 py-2 shadow-xs
                placeholder:text-text-3 focus:outline-none
                focus:border-accent focus:ring-2 focus:ring-accent/25
                transition-all"
                placeholder="Краткое описание"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>Категория</Label>
                <Input
                  value={v.category}
                  onChange={(e) => set('category', e.target.value)}
                  placeholder="Куртки"
                />
              </div>
              <div>
                <Label>Цвет</Label>
                <Input
                  value={v.color}
                  onChange={(e) => set('color', e.target.value)}
                  placeholder="Чёрный"
                />
              </div>
              <div>
                <Label>Группа</Label>
                <Input
                  value={v.group}
                  onChange={(e) => set('group', e.target.value)}
                  placeholder="Верхняя одежда"
                />
              </div>
            </div>
          </>
        )}

        <section>
          <div className="flex items-center justify-between mb-2">
            <div className="eyebrow">Размеры</div>
            <button
              onClick={addSize}
              className="text-12 text-accent-2 hover:text-accent
              inline-flex items-center gap-1"
            >
              <Plus className="h-3 w-3" /> добавить
            </button>
          </div>
          {v.sizes.length === 0 && (
            <div className="text-12 text-text-3 py-3">
              нет размеров — товар без характеристик
            </div>
          )}
          {v.sizes.map((s, i) => (
            <div
              key={i}
              className="grid grid-cols-[100px_100px_1fr_auto]
              gap-2 mb-2"
            >
              <Input
                placeholder="global"
                value={s.global}
                onChange={(e) =>
                  setSize(i, { global: e.target.value })
                }
              />
              <Input
                placeholder="RU"
                value={s.ru}
                onChange={(e) =>
                  setSize(i, { ru: e.target.value })
                }
              />
              <Input
                placeholder="штрихкод"
                className="font-mono"
                value={s.barcode}
                onChange={(e) =>
                  setSize(i, { barcode: e.target.value })
                }
              />
              <Button
                variant="destructive"
                size="sm"
                onClick={() => removeSize(i)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </section>

        {mode === 'create' && (
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="eyebrow">Фото (URL)</div>
              <button
                onClick={addPhoto}
                className="text-12 text-accent-2 hover:text-accent
                inline-flex items-center gap-1"
              >
                <Plus className="h-3 w-3" /> добавить
              </button>
            </div>
            {v.photos.map((u, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <Input
                  placeholder="https://..."
                  value={u}
                  onChange={(e) => setPhoto(i, e.target.value)}
                />
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => removePhoto(i)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </section>
        )}

        {error && (
          <div
            className="text-13 text-negative bg-negative-tint
            rounded-lg px-3 py-2"
          >
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button
            onClick={submit}
            disabled={
              submitting ||
              (mode === 'create' &&
                (articleStatus === 'taken' ||
                  !v.article ||
                  !v.name ||
                  !v.price))
            }
          >
            {submitting ? 'Сохраняю…' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function ArticleBadge({
  status,
}: {
  status: 'checking' | 'free' | 'taken';
}) {
  if (status === 'checking') {
    return (
      <span
        className="absolute right-2 top-1/2 -translate-y-1/2
        text-11 text-text-3"
      >
        проверяю…
      </span>
    );
  }
  if (status === 'free') {
    return (
      <span
        className="absolute right-2 top-1/2 -translate-y-1/2
        text-11 inline-flex items-center gap-1 text-positive"
      >
        <Check className="h-3 w-3" />
        свободен
      </span>
    );
  }
  return (
    <span
      className="absolute right-2 top-1/2 -translate-y-1/2
      text-11 text-negative"
    >
      занят
    </span>
  );
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center
      overflow-y-auto bg-black/40 backdrop-blur-sm py-10"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl mx-4 rounded-2xl
        bg-surface border border-border shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between px-6 py-4
          border-b border-border"
        >
          <h2
            className="font-display text-18 font-semibold
            tracking-tight text-text"
          >
            {title}
          </h2>
          <button
            onClick={onClose}
            className="h-8 w-8 rounded-md text-text-3 hover:text-text
            hover:bg-surface-2 flex items-center justify-center"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}
