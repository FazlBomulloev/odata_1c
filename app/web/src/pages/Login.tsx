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
      className="min-h-screen bg-paper flex items-center
      justify-center px-6"
    >
      <form
        onSubmit={onSubmit}
        className="w-full max-w-[360px] hairline rounded-md
        bg-card p-6"
      >
        <div className="mb-6">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="font-mono text-14 tracking-tight text-ink">
              intreid
            </span>
            <span
              className="text-11 text-ink-3 tracking-widest uppercase"
            >
              odata
            </span>
          </div>
          <div className="text-13.5 text-ink-2">
            Войдите, чтобы работать с панелью
          </div>
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
          />
        </div>
        <div className="mb-5">
          <Label htmlFor="login-password">Пароль</Label>
          <Input
            id="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={busy}
          />
        </div>

        {error && (
          <div className="mb-4 text-12 text-negative">
            {error}
          </div>
        )}

        <Button
          type="submit"
          disabled={busy || !username || !password}
          className="w-full"
        >
          {busy ? 'Вход…' : 'Войти'}
        </Button>
      </form>
    </div>
  );
}
