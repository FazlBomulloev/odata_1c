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
      bg-bg/85 backdrop-blur border-b border-border
      flex items-center px-8"
    >
      <div className="flex items-baseline gap-3">
        <span className="text-11 text-text-3 tracking-wider uppercase">
          Панель
        </span>
        <span className="text-text-3">/</span>
        <span className="text-13 text-text font-medium">
          {PAGE_TITLES[page] ?? page}
        </span>
      </div>
      <div className="ml-auto flex items-center gap-4">
        <div className="hidden md:flex items-center gap-1.5
        text-11 text-text-3">
          <span className="font-mono text-text-2">
            Intreid_UNF_Copy4
          </span>
        </div>
        <div className="h-4 w-px bg-border hidden md:block" />
        <SyncStatus />
      </div>
    </div>
  );
}
