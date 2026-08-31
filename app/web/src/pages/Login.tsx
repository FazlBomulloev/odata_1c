import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input, Label } from '@/components/ui/input';
import { useAuth } from '@/lib/auth';

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-stretch">
      <div
        className="hidden lg:flex flex-1 relative overflow-hidden
        bg-nav-bg text-nav-text"
      >
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(circle at 25% 25%, ' +
              'rgba(8,145,178,0.32), transparent 55%),' +
              'radial-gradient(circle at 75% 80%, ' +
              'rgba(16,185,129,0.22), transparent 55%)',
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.03) 1px, ' +
              'transparent 1px),' +
              'linear-gradient(90deg, rgba(255,255,255,0.03) 1px, ' +
              'transparent 1px)',
            backgroundSize: '32px 32px',
          }}
        />
        <div
          className="relative z-10 flex flex-col justify-between
          p-14 max-w-[560px]"
        >
          <div className="flex items-center gap-3">
            <div
              className="h-11 w-11 rounded-xl grad-accent
              flex items-center justify-center
              shadow-[0_10px_30px_-4px_rgba(8,145,178,0.55)]"
            >
              <span
                className="font-display text-[20px] font-bold
                text-white leading-none"
              >
                i
              </span>
            </div>
            <div>
              <div
                className="font-display text-[17px] font-semibold
                tracking-tight text-nav-text"
              >
                intreid
              </div>
              <div
                className="text-[10px] text-nav-text-3 tracking-widest
                uppercase"
              >
                odata gateway
              </div>
            </div>
          </div>

          <div>
            <div className="eyebrow mb-4 !text-nav-text-3
            flex items-center gap-2">
              <span className="h-1 w-1 rounded-full grad-accent" />
              Что внутри
            </div>
            <h2
              className="font-display text-[44px] font-semibold
              tracking-tight leading-[1.05] mb-5"
            >
              Ваши цифры,
              <br />
              <span className="grad-text">в одном окне</span>.
            </h2>
            <p
              className="text-14 text-nav-text-2 leading-relaxed
              max-w-md"
            >
              Продажи по каналам, движения по складам, остатки
              и валовая прибыль из 1С УНФ — с фильтрами, поиском
              и мгновенным откликом.
            </p>

            <div className="mt-10 grid grid-cols-3 gap-4">
              {[
                ['WB · Ozon · Lamoda', 'каналы'],
                ['по размерам', 'прибыль'],
                ['каждые 2ч', 'синк'],
              ].map(([v, k]) => (
                <div key={k}>
                  <div
                    className="font-display text-[15px] font-semibold
                    text-nav-text"
                  >
                    {v}
                  </div>
                  <div
                    className="text-11 text-nav-text-3 mt-1
                    tracking-wider uppercase"
                  >
                    {k}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="text-11 text-nav-text-3 tabular">
            <span className="font-mono">Intreid_UNF_Copy4</span>
          </div>
        </div>
      </div>

      <div
        className="flex-1 flex items-center justify-center px-6
        lg:max-w-[560px]"
      >
        <form
          onSubmit={onSubmit}
          className="w-full max-w-[380px]"
        >
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2.5">
              <div
                className="h-9 w-9 rounded-lg grad-accent
                flex items-center justify-center"
              >
                <span
                  className="font-display text-15 font-bold
                  text-white leading-none"
                >
                  i
                </span>
              </div>
              <span className="font-display text-15 font-semibold
              tracking-tight text-text">
                intreid
              </span>
            </div>
          </div>

          <div className="mb-8">
            <div className="eyebrow mb-3 flex items-center gap-2">
              <span className="h-1 w-1 rounded-full grad-accent" />
              Вход
            </div>
            <h1
              className="font-display text-32 font-semibold
              tracking-tight text-text"
            >
              С возвращением
            </h1>
            <p className="text-13.5 text-text-2 mt-2">
              Войдите под своей учёткой.
            </p>
          </div>

          <div className="mb-4">
            <Label htmlFor="login-username">Логин</Label>
            <Input
              id="login-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
              disabled={busy}
              className="h-11 text-14"
            />
          </div>
          <div className="mb-6">
            <Label htmlFor="login-password">Пароль</Label>
            <Input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              disabled={busy}
              className="h-11 text-14"
            />
          </div>

          {error && (
            <div
              className="mb-5 text-12 text-negative bg-negative-tint
              border border-negative/20 rounded-lg px-3 py-2"
            >
              {error}
            </div>
          )}

          <Button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full h-11 text-14"
          >
            {busy ? 'Вход…' : 'Войти в панель'}
          </Button>

          <div
            className="mt-10 text-11 text-text-3 text-center tabular"
          >
            Нет учётки? Обратитесь к владельцу панели.
          </div>
        </form>
      </div>
    </div>
  );
}
