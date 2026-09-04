import { useEffect, useRef, useState } from 'react';
import {
  X, Plus, Trash2, Sparkles, Check, Upload, Link as LinkIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import {
  api, ApiError,
  type ProductSizePayload, type ProductSizeShort,
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
  existingSizes: ProductSizeShort[];
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
  existingSizes: [],
  sizes: [],
  photos: [],
};

const MAX_PHOTO_BYTES = 5 * 1024 * 1024;

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
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const addPhotoUrl = () =>
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

  const readFileAsDataUrl = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(fr.result as string);
      fr.onerror = () => reject(fr.error);
      fr.readAsDataURL(file);
    });

  const onFilesPicked = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const list = Array.from(files);
    const oversized = list.find((f) => f.size > MAX_PHOTO_BYTES);
    if (oversized) {
      setError(
        `Файл "${oversized.name}" больше 5 МБ — уменьшите размер`,
      );
      return;
    }
    setError(null);
    try {
      const urls = await Promise.all(
        list.map((f) => readFileAsDataUrl(f)),
      );
      setV((s) => ({ ...s, photos: [...s.photos, ...urls] }));
    } catch (e) {
      setError(`Не удалось прочитать файл: ${(e as Error).message}`);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

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
        await api.productUpdate(initial.article, {
          name: v.name || undefined,
          description: v.description,
          price: v.price ? Number(v.price) : undefined,
          category: v.category || undefined,
          group: v.group || undefined,
          sizes: cleanSizes.length ? cleanSizes : undefined,
          photos: cleanPhotos.length ? cleanPhotos : undefined,
        });
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
          <div
            className="grid gap-3 items-end
            grid-cols-[1fr_auto_1.4fr]"
          >
            <div>
              <Label>Префикс артикула</Label>
              <Input
                value={v.articlePrefix}
                onChange={(e) =>
                  set('articlePrefix', e.target.value)
                }
                placeholder="например 180"
                className="font-mono"
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

        {mode === 'edit' && initial?.article && (
          <div
            className="text-11 text-text-3 -mb-3
            font-mono tabular"
          >
            артикул{' '}
            <span className="text-text-2">
              {initial.article}
            </span>
          </div>
        )}

        <div className="grid grid-cols-[2fr_1fr] gap-3">
          <div>
            <Label>Название</Label>
            <Input
              value={v.name}
              onChange={(e) => set('name', e.target.value)}
              placeholder="Куртка мужская"
            />
          </div>
          <div>
            <Label>Цена, ₽</Label>
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
            placeholder="Краткое описание — идёт в поле «Комментарий»"
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
            <Label>
              Цвет
              {mode === 'edit' && (
                <span className="text-11 text-text-3 ml-1">
                  (только при создании)
                </span>
              )}
            </Label>
            <Input
              value={v.color}
              onChange={(e) => set('color', e.target.value)}
              placeholder="Чёрный"
              disabled={mode === 'edit'}
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

          {v.existingSizes.length > 0 && (
            <div className="mb-3">
              <div
                className="text-11 text-text-3 mb-1.5"
              >
                уже заведены — редактировать нельзя,
                можно добавить новые ниже
              </div>
              <div className="flex flex-wrap gap-1">
                {v.existingSizes.map((s, i) => (
                  <span
                    key={i}
                    className="text-11 font-mono tabular
                    px-2 py-1 rounded bg-surface-2
                    border border-border"
                  >
                    {s.global && s.ru
                      ? `${s.global} · ${s.ru}`
                      : s.ru || s.global || '?'}
                  </span>
                ))}
              </div>
            </div>
          )}

          {v.sizes.length === 0 &&
           v.existingSizes.length === 0 && (
            <div className="text-12 text-text-3 py-3">
              нет размеров — товар без характеристик
            </div>
          )}
          {v.sizes.map((s, i) => (
            <div
              key={i}
              className="grid gap-2 mb-2
              grid-cols-[1fr_1fr_2fr_auto]"
            >
              <Input
                placeholder="global (S/M/L/2XL)"
                value={s.global}
                onChange={(e) =>
                  setSize(i, { global: e.target.value })
                }
              />
              <Input
                placeholder="RU (44/46/48)"
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

        <section>
          <div className="flex items-center justify-between mb-2">
            <div className="eyebrow">
              Фото
              {mode === 'edit' && (
                <span className="ml-1 text-11 text-text-3
                normal-case">
                  добавить новые
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-12 text-accent-2 hover:text-accent
                inline-flex items-center gap-1"
              >
                <Upload className="h-3 w-3" /> выбрать файлы
              </button>
              <button
                onClick={addPhotoUrl}
                className="text-12 text-accent-2 hover:text-accent
                inline-flex items-center gap-1"
              >
                <LinkIcon className="h-3 w-3" /> добавить URL
              </button>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*"
            className="hidden"
            onChange={(e) => void onFilesPicked(e.target.files)}
          />

          {v.photos.length === 0 && (
            <div className="text-12 text-text-3 py-3">
              фото не добавлены
            </div>
          )}

          {v.photos.length > 0 && (
            <div
              className="grid gap-2"
              style={{
                gridTemplateColumns:
                  'repeat(auto-fill, minmax(120px, 1fr))',
              }}
            >
              {v.photos.map((p, i) => (
                <PhotoTile
                  key={i}
                  value={p}
                  index={i}
                  onChange={(u) => setPhoto(i, u)}
                  onRemove={() => removePhoto(i)}
                />
              ))}
            </div>
          )}
        </section>

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

function PhotoTile({
  value, index, onChange, onRemove,
}: {
  value: string;
  index: number;
  onChange: (v: string) => void;
  onRemove: () => void;
}) {
  const isData = value.startsWith('data:');
  const isUrl = /^https?:\/\//.test(value);
  return (
    <div
      className="relative rounded-lg overflow-hidden
      border border-border bg-surface-2 aspect-square
      flex flex-col"
    >
      <div className="flex-1 flex items-center justify-center
      relative overflow-hidden">
        {isData || isUrl ? (
          <img
            src={value}
            alt={`photo ${index}`}
            className="w-full h-full object-cover"
          />
        ) : (
          <input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="https://..."
            className="w-full h-full text-11 px-2 bg-transparent
            border-0 focus:outline-none placeholder:text-text-3"
          />
        )}
        <button
          onClick={onRemove}
          className="absolute top-1 right-1 h-6 w-6 rounded-md
          bg-negative/90 text-white flex items-center
          justify-center opacity-90 hover:opacity-100"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
      <div
        className="text-10 text-text-3 px-2 py-1 border-t
        border-border truncate font-mono"
      >
        {isData ? 'файл' : isUrl ? 'URL' : 'пусто'}
      </div>
    </div>
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
