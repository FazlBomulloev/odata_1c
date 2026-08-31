import { SyncStatus } from '@/components/SyncStatus';

const PAGE_TITLES: Record<string, string> = {
  sales: 'Продажи',
  gross_profit: 'Валовая прибыль',
  movements: 'Движения',
  stock: 'Остатки',
  history: 'История запросов',
  users: 'Команда',
};

export function Topbar({ page }: { page: string }) {
  return (
    <div
      className="sticky top-0 z-30 h-[var(--topbar-h)]
      glass border-b border-border
      flex items-center px-8"
    >
      <div className="flex items-baseline gap-2.5">
        <span
          className="text-11 text-text-3 tracking-[0.14em] uppercase"
        >
          Панель
        </span>
        <span className="text-text-3">/</span>
        <span className="text-13.5 text-text font-medium">
          {PAGE_TITLES[page] ?? page}
        </span>
      </div>
      <div className="ml-auto flex items-center gap-4">
        <div
          className="hidden md:flex items-center gap-1.5 px-2.5 h-6
          rounded-md bg-surface-2 border border-border"
        >
          <span
            className="h-1.5 w-1.5 rounded-full bg-info"
          />
          <span className="text-11 text-text-2 tabular">
            Intreid_UNF_Copy4
          </span>
        </div>
        <SyncStatus />
      </div>
    </div>
  );
}
