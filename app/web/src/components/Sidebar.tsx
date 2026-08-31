import {
  ShoppingBag, TrendingUp, ArrowLeftRight,
  Package, Users as UsersIcon,
  LogOut, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth';

export type PageKey =
  | 'sales' | 'gross_profit' | 'movements'
  | 'stock' | 'users';

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
      bg-nav-bg text-nav-text flex flex-col
      border-r border-nav-border"
    >
      <div className="px-5 pt-6 pb-7">
        <button
          onClick={() => onSelect('sales')}
          className="group flex items-center gap-3"
        >
          <div
            className="h-9 w-9 rounded-xl grad-accent
            flex items-center justify-center
            shadow-[0_8px_24px_-6px_rgba(8,145,178,0.6)]
            transition-transform duration-200
            group-hover:scale-105 group-hover:rotate-3"
          >
            <span
              className="font-display text-[18px] font-bold
              text-white leading-none"
            >
              i
            </span>
          </div>
          <div className="flex flex-col items-start leading-none">
            <span
              className="font-display text-[15px] font-semibold
              tracking-tight text-nav-text"
            >
              intreid
            </span>
            <span
              className="text-[10px] text-nav-text-3 tracking-[0.15em]
              uppercase mt-0.5"
            >
              odata gateway
            </span>
          </div>
        </button>
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {visible.map((it) => {
          const Icon = it.icon;
          const active = current === it.key;
          return (
            <button
              key={it.key}
              onClick={() => onSelect(it.key)}
              className={cn(
                'group w-full flex items-center gap-3 px-3 h-10',
                'rounded-lg text-13 transition-all duration-200',
                'relative overflow-hidden',
                active
                  ? 'bg-nav-surface text-nav-text'
                  : 'text-nav-text-2 hover:text-nav-text ' +
                    'hover:bg-nav-surface/70',
              )}
            >
              {active && (
                <>
                  <span
                    className="absolute left-0 top-1.5 bottom-1.5
                    w-[3px] rounded-r-full grad-accent"
                  />
                  <span
                    className="absolute inset-0 opacity-40
                    pointer-events-none"
                    style={{
                      backgroundImage:
                        'linear-gradient(90deg, ' +
                        'rgba(8,145,178,0.14) 0%, ' +
                        'transparent 60%)',
                    }}
                  />
                </>
              )}
              <Icon
                className={cn(
                  'h-4 w-4 transition-all duration-200 shrink-0',
                  'relative z-10',
                  active
                    ? 'text-accent-2'
                    : 'text-nav-text-3 group-hover:text-nav-text',
                )}
                strokeWidth={1.75}
              />
              <span className="relative z-10 truncate">
                {it.label}
              </span>
              {active && (
                <ChevronRight
                  className="ml-auto h-3.5 w-3.5 text-nav-text-3
                  relative z-10"
                />
              )}
            </button>
          );
        })}
      </nav>

      <div className="px-3 pb-4 pt-3 border-t border-nav-border">
        {user && (
          <div
            className="flex items-center gap-3 px-3 py-2 group
            rounded-lg hover:bg-nav-surface/60 transition-colors"
          >
            <div
              className="h-9 w-9 rounded-full grad-accent
              flex items-center justify-center
              text-12 font-display font-semibold text-white uppercase
              shadow-[0_4px_12px_-4px_rgba(8,145,178,0.5)]"
            >
              {user.username.slice(0, 2)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-12.5 text-nav-text truncate
              font-medium">
                {user.username}
              </div>
              <div className="text-[10px] text-nav-text-3
              tracking-wider uppercase mt-0.5">
                {user.role === 'owner' ? 'владелец' : 'сотрудник'}
              </div>
            </div>
            <button
              onClick={() => void logout()}
              title="Выйти"
              className="opacity-0 group-hover:opacity-100
              transition-opacity h-7 w-7 rounded-md
              text-nav-text-3 hover:text-white
              hover:bg-negative/80
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
