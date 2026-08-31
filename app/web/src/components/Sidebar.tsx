import {
  ShoppingBag, TrendingUp, ArrowLeftRight,
  Package, History as HistoryIcon, Users as UsersIcon,
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth';

export type PageKey =
  | 'sales' | 'gross_profit' | 'movements'
  | 'stock' | 'history' | 'users';

type Item = {
  key: PageKey;
  label: string;
  icon: typeof ShoppingBag;
  ownerOnly?: boolean;
};

const items: Item[] = [
  { key: 'sales', label: 'Продажи', icon: ShoppingBag },
  { key: 'gross_profit', label: 'Прибыль', icon: TrendingUp },
  { key: 'movements', label: 'Движения', icon: ArrowLeftRight },
  { key: 'stock', label: 'Остатки', icon: Package },
  { key: 'history', label: 'История', icon: HistoryIcon },
  { key: 'users', label: 'Команда', icon: UsersIcon, ownerOnly: true },
];

export function Sidebar({
  current, onSelect,
}: {
  current: PageKey;
  onSelect: (k: PageKey) => void;
}) {
  const { user, logout } = useAuth();
  const isOwner = user?.role === 'owner';
  const visible = items.filter((i) => !i.ownerOnly || isOwner);

  return (
    <aside
      className="fixed inset-y-0 left-0 w-[var(--sidebar-w)]
      bg-bg-2 border-r border-border flex flex-col"
    >
      <div className="px-5 pt-5 pb-6">
        <button
          onClick={() => onSelect('sales')}
          className="group flex items-center gap-2.5"
        >
          <div
            className="h-8 w-8 rounded-lg bg-accent
            flex items-center justify-center
            shadow-[0_0_20px_-6px_var(--accent)]
            transition-transform group-hover:scale-105"
          >
            <span
              className="font-display text-[16px] font-bold
              text-accent-fg leading-none"
            >
              i
            </span>
          </div>
          <div className="flex flex-col items-start leading-none">
            <span
              className="font-display text-14 font-semibold
              tracking-tight text-text"
            >
              intreid
            </span>
            <span
              className="text-10 text-text-3 tracking-widest
              uppercase mt-0.5"
            >
              odata
            </span>
          </div>
        </button>
      </div>

      <nav className="flex-1 px-3 space-y-0.5">
        {visible.map((it) => {
          const Icon = it.icon;
          const active = current === it.key;
          return (
            <button
              key={it.key}
              onClick={() => onSelect(it.key)}
              className={cn(
                'group w-full flex items-center gap-3 px-3 h-9',
                'rounded-md text-13 transition-all duration-150',
                'relative',
                active
                  ? 'bg-surface text-text'
                  : 'text-text-2 hover:text-text hover:bg-surface',
              )}
            >
              {active && (
                <span
                  className="absolute left-0 top-1.5 bottom-1.5 w-[2px]
                  rounded-r-full bg-accent"
                />
              )}
              <Icon
                className={cn(
                  'h-4 w-4 transition-colors shrink-0',
                  active ? 'text-accent' : 'text-text-3',
                )}
                strokeWidth={1.75}
              />
              <span className="truncate">{it.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="px-3 pb-4 pt-3 border-t border-border">
        {user && (
          <div className="flex items-center gap-2.5 px-3 py-2 group">
            <div
              className="h-8 w-8 rounded-full bg-surface-2
              border border-border flex items-center justify-center
              text-12 font-display font-semibold text-text uppercase"
            >
              {user.username.slice(0, 2)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-12 text-text truncate">
                {user.username}
              </div>
              <div className="text-10 text-text-3 tracking-wide uppercase">
                {user.role === 'owner' ? 'владелец' : 'сотрудник'}
              </div>
            </div>
            <button
              onClick={() => void logout()}
              title="Выйти"
              className="opacity-0 group-hover:opacity-100
              transition-opacity h-7 w-7 rounded-md
              text-text-3 hover:text-negative hover:bg-negative-tint
              flex items-center justify-center"
            >
              <LogOut className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
