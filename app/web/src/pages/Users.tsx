import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input, Label, Select } from '@/components/ui/input';
import { api, ApiError, type CurrentUser, type Role } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { fmtDate } from '@/lib/utils';

export function UsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<Role>('employee');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await api.listUsers());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      await api.createUser(newUsername.trim(), newPassword, newRole);
      setNewUsername('');
      setNewPassword('');
      setNewRole('employee');
      await reload();
    } catch (err) {
      setCreateError(
        err instanceof Error ? err.message : String(err),
      );
    } finally {
      setCreating(false);
    }
  }

  async function onToggleActive(u: CurrentUser) {
    try {
      await api.patchUser(u.id, { is_active: !u.is_active });
      await reload();
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  }

  async function onResetPassword(u: CurrentUser) {
    const p = window.prompt(
      `Новый пароль для «${u.username}» (мин. 6 символов):`,
    );
    if (!p) return;
    if (p.length < 6) {
      alert('Слишком короткий пароль');
      return;
    }
    try {
      await api.patchUser(u.id, { password: p });
      alert('Пароль изменён');
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  }

  async function onDelete(u: CurrentUser) {
    if (!window.confirm(`Удалить «${u.username}»?`)) return;
    try {
      await api.deleteUser(u.id);
      await reload();
    } catch (err) {
      if (err instanceof ApiError) {
        alert(err.message);
      } else {
        alert(String(err));
      }
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-18 font-medium text-ink mb-1">
          Пользователи
        </h1>
        <div className="text-13 text-ink-3">
          Учётки сотрудников с доступом к панели
        </div>
      </div>

      <div className="hairline rounded-md bg-card p-5 mb-8">
        <div className="eyebrow mb-3">Создать сотрудника</div>
        <form
          onSubmit={onCreate}
          className="grid grid-cols-[1fr_1fr_160px_auto] gap-3 items-end"
        >
          <div>
            <Label htmlFor="new-username">Логин</Label>
            <Input
              id="new-username"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              disabled={creating}
            />
          </div>
          <div>
            <Label htmlFor="new-password">Пароль</Label>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={creating}
            />
          </div>
          <div>
            <Label htmlFor="new-role">Роль</Label>
            <Select
              id="new-role"
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as Role)}
              disabled={creating}
            >
              <option value="employee">сотрудник</option>
              <option value="owner">владелец</option>
            </Select>
          </div>
          <Button
            type="submit"
            disabled={
              creating || !newUsername || newPassword.length < 6
            }
          >
            {creating ? 'Создание…' : 'Создать'}
          </Button>
        </form>
        {createError && (
          <div className="mt-3 text-12 text-negative">
            {createError}
          </div>
        )}
      </div>

      <div className="hairline rounded-md bg-card overflow-hidden">
        <table className="w-full text-13.5">
          <thead>
            <tr className="text-11 text-ink-3 uppercase tracking-wider">
              <th className="text-left px-4 py-3 font-medium">Логин</th>
              <th className="text-left px-4 py-3 font-medium">Роль</th>
              <th className="text-left px-4 py-3 font-medium">Статус</th>
              <th className="text-left px-4 py-3 font-medium">Создан</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-ink-3">
                  Загрузка…
                </td>
              </tr>
            )}
            {!loading && users.map((u) => {
              const isMe = me && me.id === u.id;
              return (
                <tr key={u.id} className="hairline-t">
                  <td className="px-4 py-3 text-ink">
                    {u.username}
                    {isMe && (
                      <span className="ml-2 text-11 text-ink-3">
                        (это вы)
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ink-2">
                    {u.role === 'owner' ? 'владелец' : 'сотрудник'}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        u.is_active
                          ? 'text-positive'
                          : 'text-ink-3'
                      }
                    >
                      {u.is_active ? 'активен' : 'выключен'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink-3 text-12">
                    {fmtDate(u.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex gap-1">
                      <Button
                        size="sm" variant="ghost"
                        onClick={() => onResetPassword(u)}
                      >
                        пароль
                      </Button>
                      <Button
                        size="sm" variant="ghost"
                        onClick={() => onToggleActive(u)}
                        disabled={Boolean(isMe)}
                      >
                        {u.is_active ? 'выключить' : 'включить'}
                      </Button>
                      <Button
                        size="sm" variant="destructive"
                        onClick={() => onDelete(u)}
                        disabled={Boolean(isMe)}
                      >
                        удалить
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {!loading && users.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-6 text-ink-3 text-center"
                >
                  Пусто
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {error && (
        <div className="mt-4 text-12 text-negative">
          {error}
        </div>
      )}
    </div>
  );
}
