import { useState } from 'react';
import { Sidebar, type PageKey } from '@/components/Sidebar';
import { Topbar } from '@/components/Topbar';
import { SalesPage } from '@/pages/Sales';
import { MovementsPage } from '@/pages/Movements';
import { StockPage } from '@/pages/Stock';
import { ProductsPage } from '@/pages/Products';
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
        className="min-h-screen bg-bg flex items-center
        justify-center"
      >
        <div className="flex items-center gap-3 text-13 text-text-3">
          <span
            className="h-2 w-2 rounded-full bg-accent dot-breathe"
          />
          загрузка
        </div>
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
    <div className="min-h-screen bg-bg text-text">
      <Sidebar current={current} onSelect={setPage} />
      <div className="pl-[var(--sidebar-w)]">
        <Topbar page={current} />
        <main
          key={current}
          className="max-w-[1600px] mx-auto px-8 py-8 fade-in"
        >
          {current === 'sales' && <SalesPage />}
          {current === 'gross_profit' && <GrossProfitPage />}
          {current === 'movements' && <MovementsPage />}
          {current === 'stock' && <StockPage />}
          {current === 'products' && <ProductsPage />}
          {current === 'users' && isOwner && <UsersPage />}
        </main>
      </div>
    </div>
  );
}
