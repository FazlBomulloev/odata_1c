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
    <div
      className="min-h-screen bg-bg flex items-stretch"
    >
      <div
        className="hidden lg:flex flex-1 relative overflow-hidden
        border-r border-border"
      >
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(circle at 30% 30%, ' +
              'rgba(255,184,77,0.18), transparent 50%),' +
              'radial-gradient(circle at 70% 80%, ' +
              'rgba(107,166,255,0.10), transparent 55%)',
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.02) 1px, ' +
              'transparent 1px),' +
              'linear-gradient(90deg, rgba(255,255,255,0.02) 1px, ' +
              'transparent 1px)',
            backgroundSize: '32px 32px',
          }}
        />
        <div
          className="relative z-10 flex flex-col justify-between
          p-14 max-w-[520px]"
        >
          <div className="flex items-center gap-3">
            <div
              className="h-10 w-10 rounded-lg bg-accent
              flex items-center justify-center
              shadow-[0_0_30px_-4px_var(--accent)]"
            >
              <span
                className="font-display text-[18px] font-bold
                text-accent-fg leading-none"
              >
                i
              </span>
            </div>
            <div>
              <div
                className="font-display text-16 font-semibold
                tracking-tight text-text"
              >
                intreid
              </div>
              <div
                className="text-10 text-text-3 tracking-widest
                uppercase"
              >
                odata gateway
              </div>
            </div>
          </div>

          <div>
            <div className="eyebrow mb-4">Что внутри</div>
            <h2
              className="font-display text-40 font-semibold
              tracking-tight text-text leading-tight mb-5"
            >
              Операционная панель
              <span className="text-accent">.</span>
            </h2>
            <p
              className="text-13.5 text-text-2 leading-relaxed
              max-w-md"
            >
              Продажи по каналам, движения по складам, остатки
              и валовая прибыль из 1С УНФ — в одном месте,
              с фильтрами и мгновенным откликом.
            </p>

            <div className="mt-8 grid grid-cols-3 gap-4">
              {[
                ['продажи', 'wb, ozon, розница'],
                ['прибыль', 'по размерам'],
                ['синк', 'каждые 2 часа'],
              ].map(([k, v]) => (
                <div key={k}>
                  <div
                    className="font-display text-16 font-medium
                    text-text tabular"
                  >
                    {k}
                  </div>
                  <div className="text-11 text-text-3 mt-1">
                    {v}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="text-11 text-text-3 tabular">
            <span className="font-mono">Intreid_UNF_Copy4</span>
          </div>
        </div>
      </div>

      <div
        className="flex-1 flex items-center justify-center px-6
        lg:max-w-[520px]"
      >
        <form
          onSubmit={onSubmit}
          className="w-full max-w-[360px]"
        >
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2.5">
              <div
                className="h-8 w-8 rounded-lg bg-accent
                flex items-center justify-center"
              >
                <span
                  className="font-display text-14 font-bold
                  text-accent-fg leading-none"
                >
                  i
                </span>
              </div>
              <span className="font-display text-14 font-semibold
              tracking-tight text-text">
                intreid
              </span>
            </div>
          </div>

          <div className="mb-8">
            <div className="eyebrow mb-3">Вход</div>
            <h1
              className="font-display text-28 font-semibold
              tracking-tight text-text"
            >
              С возвращением
            </h1>
            <p className="text-13 text-text-3 mt-1.5">
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
              className="h-10"
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
              className="h-10"
            />
          </div>

          {error && (
            <div
              className="mb-5 text-12 text-negative bg-negative-tint
              border border-negative/20 rounded-md px-3 py-2"
            >
              {error}
            </div>
          )}

          <Button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full h-10"
          >
            {busy ? 'Вход…' : 'Войти в панель'}
          </Button>

          <div
            className="mt-8 text-11 text-text-3 text-center tabular"
          >
            Нет учётки? Обратитесь к владельцу панели.
          </div>
        </form>
      </div>
    </div>
  );
}
