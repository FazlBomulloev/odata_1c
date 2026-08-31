import { cn } from '@/lib/utils';
import { SyncStatus } from '@/components/SyncStatus';
import { useAuth } from '@/lib/auth';

export type PageKey =
  | 'sales' | 'gross_profit' | 'movements'
  | 'stock' | 'history' | 'users';

const baseItems: { key: PageKey; label: string }[] = [
  { key: 'sales', label: 'Продажи' },
  { key: 'gross_profit', label: 'Валовая прибыль' },
  { key: 'movements', label: 'Движения' },
  { key: 'stock', label: 'Остатки' },
  { key: 'history', label: 'История' },
];

export function TopNav({
  current, onSelect,
}: {
  current: PageKey;
  onSelect: (k: PageKey) => void;
}) {
  const { user, logout } = useAuth();
  const items = user?.role === 'owner'
    ? [...baseItems, { key: 'users' as const, label: 'Пользователи' }]
    : baseItems;

  return (
    <header className="hairline-b bg-paper/95 backdrop-blur">
      <div className="max-w-[1440px] mx-auto px-8 h-14 flex items-center">
        <button
          onClick={() => onSelect('sales')}
          className="mr-10 flex items-baseline gap-2 group"
        >
          <span
            className="font-mono text-14 tracking-tight text-ink
            group-hover:text-[color:var(--accent)] transition-colors"
          >
            intreid
          </span>
          <span className="text-11 text-ink-3 tracking-widest uppercase">
            odata
          </span>
        </button>

        <nav className="flex items-center gap-1">
          {items.map((it) => {
            const active = current === it.key;
            return (
              <button
                key={it.key}
                onClick={() => onSelect(it.key)}
                className={cn(
                  'relative px-3 h-14 text-13.5 transition-colors',
                  active
                    ? 'text-ink font-medium'
                    : 'text-ink-3 hover:text-ink',
                )}
              >
                {it.label}
                {active && (
                  <span
                    className="absolute left-3 right-3 bottom-0 h-px
                    bg-[color:var(--accent)]"
                  />
                )}
              </button>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-6">
          <span className="text-11 text-ink-3">
            База{' '}
            <span className="font-mono text-ink-2">
              Intreid_UNF_Copy4
            </span>
          </span>
          <SyncStatus />
          {user && (
            <div className="flex items-center gap-2 text-11">
              <span className="text-ink-3">
                <span className="text-ink-2">{user.username}</span>
                <span className="ml-1 text-ink-3">
                  · {user.role === 'owner' ? 'владелец' : 'сотрудник'}
                </span>
              </span>
              <button
                onClick={() => void logout()}
                className={cn(
                  'text-11 px-2 h-6 rounded border border-rule',
                  'text-ink-2 hover:text-ink hover:bg-wash',
                  'transition-colors',
                )}
                title="Выйти из панели"
              >
                выйти
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
