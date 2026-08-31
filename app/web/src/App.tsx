import { useState } from 'react';
import { TopNav, type PageKey } from '@/components/TopNav';
import { SalesPage } from '@/pages/Sales';
import { MovementsPage } from '@/pages/Movements';
import { StockPage } from '@/pages/Stock';
import { HistoryPage } from '@/pages/History';
import { UsersPage } from '@/pages/Users';
import { LoginPage } from '@/pages/Login';
import { GrossProfitPage } from '@/pages/GrossProfit';
import { AuthProvider, useAuth } from '@/lib/auth';

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}

function AppInner() {
  const { user, loading } = useAuth();
  const [page, setPage] = useState<PageKey>('sales');

  if (loading) {
    return (
      <div
        className="min-h-screen bg-paper flex items-center
        justify-center text-13 text-ink-3"
      >
        Загрузка…
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  const isOwner = user.role === 'owner';
  const current: PageKey =
    page === 'users' && !isOwner ? 'sales' : page;

  return (
    <div className="min-h-screen bg-paper">
      <TopNav current={current} onSelect={setPage} />
      <main className="max-w-[1440px] mx-auto px-8 py-10">
        {current === 'sales' && <SalesPage />}
        {current === 'gross_profit' && <GrossProfitPage />}
        {current === 'movements' && <MovementsPage />}
        {current === 'stock' && <StockPage />}
        {current === 'history' && <HistoryPage />}
        {current === 'users' && isOwner && <UsersPage />}
      </main>
      <footer className="max-w-[1440px] mx-auto px-8 pb-8 mt-16">
        <div className="hairline-t pt-4 flex items-center
        justify-between text-11 text-ink-3">
          <span>
            intreid · odata gateway · v0.3
          </span>
          <span className="font-mono">
            Intreid_UNF_Copy4
          </span>
        </div>
      </footer>
    </div>
  );
}
