const BASE = (import.meta.env.VITE_API_BASE as string) || '';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export type RunResult<T = Record<string, unknown>> = {
  run_id: number;
  duration_ms: number;
  record_count: number;
  records: T[];
};

export type RunSummary = {
  id: number;
  method: string;
  status: 'running' | 'ok' | 'error';
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  record_count: number | null;
  error: string | null;
  params: Record<string, unknown>;
};

export type RunDetail = RunSummary & {
  payload: Record<string, unknown>[] | null;
};

export type CatalogItem = { ref: string; name: string };

export type SyncRunStatus = {
  kind: string;
  status: 'running' | 'ok' | 'error';
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  record_count: number | null;
  error: string | null;
};

export type SyncStatusResponse = {
  interval_hours: number;
  runs: SyncRunStatus[];
};

export type ProductListItem = {
  ref_key: string;
  article: string;
  name: string;
  full_name: string;
  group_key: string;
  category_key: string;
  photo_key: string;
  price: number;
  deletion_mark: boolean;
};

export type ProductSizePayload = {
  global: string;
  ru: string;
  barcode: string;
};

export type ProductCreatePayload = {
  article?: string | null;
  article_prefix?: string | null;
  name: string;
  description?: string;
  price: number;
  category?: string;
  color?: string;
  group?: string;
  sizes?: ProductSizePayload[];
  photos?: string[];
};

export type ProductUpdatePayload = {
  name?: string;
  price?: number;
  sizes?: ProductSizePayload[];
};

export type ProductDetail = {
  nomenclature: Record<string, unknown>;
  characteristics: Record<string, unknown>[];
  barcodes: Record<string, unknown>[];
  prices: Record<string, unknown>[];
  photos: {
    Ref_Key: string;
    Description: string;
    Расширение: string;
    Размер: number;
  }[];
};

export type Role = 'owner' | 'employee';

export type CurrentUser = {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  created_by: number | null;
};

async function req<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: 'include',
    headers: body !== undefined
      ? { 'Content-Type': 'application/json' }
      : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };
  const r = await fetch(`${BASE}${path}`, init);
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const j = await r.json();
      if (j && typeof j.detail === 'string') msg = j.detail;
    } catch {
      const text = await r.text().catch(() => '');
      if (text) msg = text;
    }
    if (r.status === 401 && !path.startsWith('/api/auth/')) {
      // Сессия истекла посреди работы — просим Auth перечитать.
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
    throw new ApiError(r.status, msg);
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  return req<T>('POST', path, body);
}

async function get<T>(path: string): Promise<T> {
  return req<T>('GET', path);
}

export const api = {
  marketplaceSales: (
    date_from: string,
    date_to: string,
    channel?: string | null,
  ) =>
    post<RunResult>('/api/sales/marketplace', {
      date_from,
      date_to,
      channel: channel || null,
    }),
  retailSales: (date_from: string, date_to: string) =>
    post<RunResult>('/api/sales/retail', { date_from, date_to }),
  allSales: (date_from: string, date_to: string) =>
    post<RunResult>('/api/sales/all', { date_from, date_to }),
  movements: (params: {
    date_from: string;
    date_to: string;
    kind: string;
    organization?: string;
    warehouse?: string;
  }) =>
    post<RunResult>('/api/movements', {
      organization: '',
      warehouse: '',
      ...params,
    }),
  stock: (params: {
    warehouse?: string;
    organization?: string;
    nomenclature?: string;
    only_positive?: boolean;
  }) =>
    post<RunResult>('/api/stock', {
      warehouse: '',
      organization: '',
      nomenclature: '',
      only_positive: true,
      ...params,
    }),
  stockByArticle: (article: string) =>
    post<RunResult>('/api/stock/by-article', { article }),
  warehouses: () => get<CatalogItem[]>('/api/catalog/warehouses'),
  organizations: () =>
    get<CatalogItem[]>('/api/catalog/organizations'),
  runs: (limit = 100) =>
    get<RunSummary[]>(`/api/runs?limit=${limit}`),
  run: (id: number) => get<RunDetail>(`/api/runs/${id}`),
  deleteRun: async (id: number) => {
    const r = await fetch(`${BASE}/api/runs/${id}`, {
      method: 'DELETE',
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  },
  syncStatus: () => get<SyncStatusResponse>('/api/sync/status'),
  syncRefresh: (full = false) =>
    post<{ ok: boolean; started: boolean; full: boolean }>(
      `/api/sync/refresh${full ? '?full=true' : ''}`,
      {},
    ),

  grossProfit: (params: {
    date_from: string;
    date_to: string;
    article?: string | null;
    warehouse?: string;
    organization?: string;
    contractor?: string;
    group_by?: string[];
  }) =>
    post<RunResult>('/api/gross-profit', {
      warehouse: '',
      organization: '',
      contractor: '',
      group_by: ['article', 'size'],
      ...params,
    }),

  authLogin: (username: string, password: string) =>
    post<CurrentUser>('/api/auth/login', { username, password }),
  authLogout: () => post<{ ok: boolean }>('/api/auth/logout', {}),
  authMe: () => get<CurrentUser>('/api/auth/me'),

  productsList: (params: {
    prefix?: string;
    limit?: number;
    offset?: number;
    only_active?: boolean;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.prefix) qs.set('prefix', params.prefix);
    if (params.limit != null) qs.set('limit', String(params.limit));
    if (params.offset != null) qs.set('offset', String(params.offset));
    if (params.only_active != null) {
      qs.set('only_active', String(params.only_active));
    }
    const q = qs.toString();
    return get<ProductListItem[]>(
      `/api/products${q ? `?${q}` : ''}`,
    );
  },
  productNextArticle: (prefix: string) =>
    get<{ article: string }>(
      `/api/products/next-article?prefix=${encodeURIComponent(prefix)}`,
    ),
  productExists: (article: string) =>
    get<{ article: string; exists: boolean }>(
      `/api/products/exists?article=${encodeURIComponent(article)}`,
    ),
  productSearch: (prefix: string) =>
    get<{ prefix: string; articles: string[] }>(
      `/api/products/search?prefix=${encodeURIComponent(prefix)}`,
    ),
  productGet: (article: string) =>
    get<ProductDetail>(
      `/api/products/${encodeURIComponent(article)}`,
    ),
  productCreate: (data: ProductCreatePayload) =>
    post<{ article: string; result: unknown }>(
      '/api/products', data,
    ),
  productUpdate: (article: string, data: ProductUpdatePayload) =>
    req<unknown>(
      'PATCH', `/api/products/${encodeURIComponent(article)}`, data,
    ),
  productDelete: (article: string) =>
    req<{ ok: boolean }>(
      'DELETE', `/api/products/${encodeURIComponent(article)}`,
    ),
  productPhotoUrl: (fileKey: string) =>
    `${BASE}/api/products/photo/${encodeURIComponent(fileKey)}`,

  listUsers: () => get<CurrentUser[]>('/api/users'),
  createUser: (
    username: string, password: string, role: Role = 'employee',
  ) => post<CurrentUser>('/api/users', { username, password, role }),
  patchUser: (
    id: number,
    patch: { password?: string; is_active?: boolean },
  ) => req<CurrentUser>('PATCH', `/api/users/${id}`, patch),
  deleteUser: (id: number) =>
    req<{ ok: boolean }>('DELETE', `/api/users/${id}`),
};
