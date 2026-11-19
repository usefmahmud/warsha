/** Boards home: list, create, rename, delete, share links. */

import { useCallback, useEffect, useState } from 'react';
import { ApiError, api } from '../api';
import { Icon } from '../components/Icons';
import { Button, IconButton, Modal, Spinner, Toast } from '../components/ui';
import { PALETTE, type BoardSummary } from '../types';

export function BoardList({ onOpen }: { onOpen: (id: string) => void }) {
  const [boards, setBoards] = useState<BoardSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState<string>('#6366f1');
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<BoardSummary | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [deleting, setDeleting] = useState<BoardSummary | null>(null);

  const load = useCallback(async () => {
    try {
      setBoards(await api.listBoards());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.messageAr : 'مش قادر أجيب البوردات');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2400);
    return () => window.clearTimeout(t);
  }, [toast]);

  const create = async () => {
    const name = newName.trim() || 'بورد جديد';
    setBusy(true);
    try {
      const board = await api.createBoard({ name, color: newColor });
      setCreating(false);
      setNewName('');
      onOpen(board.id);
    } catch (e) {
      setToast(e instanceof ApiError ? e.messageAr : 'مش قادر أعمل بورد');
    } finally {
      setBusy(false);
    }
  };

  const rename = async () => {
    if (!renaming) return;
    const name = renameValue.trim();
    if (!name) return;
    try {
      await api.patchBoard(renaming.id, { name });
      setRenaming(null);
      await load();
      setToast('اتغيّر الاسم');
    } catch {
      setToast('مش قادر أعدّل الاسم');
    }
  };

  const remove = async () => {
    if (!deleting) return;
    try {
      await api.deleteBoard(deleting.id);
      setDeleting(null);
      await load();
      setToast('اتحذف البورد');
    } catch {
      setToast('مش قادر أحذف البورد');
    }
  };

  const share = async (board: BoardSummary) => {
    try {
      const info = await api.share(board.id);
      await navigator.clipboard.writeText(`${window.location.origin}/#/s/${info.share_token}`);
      setToast('اتنسخ رابط المشاركة');
      await load();
    } catch {
      setToast('مش قادر أعمل رابط مشاركة');
    }
  };

  return (
    <div className="min-h-full bg-ink-950">
      <div className="mx-auto w-full max-w-6xl px-4 pb-16 pt-6 sm:px-6">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-600 shadow-lg shadow-brand-600/30">
              <Icon name="pen" size={22} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-ink-200">وايت بورد</h1>
              <p className="text-[11px] text-ink-400">ارسم أفكارك، نظّمها، وشاركها في لحظة</p>
            </div>
          </div>
          <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
            بورد جديد
          </Button>
        </header>

        {boards === null && !error && <Spinner label="بيحمّل بورداتك…" />}

        {error && (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
            {error}
            <button onClick={() => void load()} className="ms-3 underline">
              حاول تاني
            </button>
          </div>
        )}

        {boards && boards.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-4 rounded-3xl border border-dashed border-ink-700 bg-ink-900/40 px-6 py-20 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-ink-850 text-ink-400">
              <Icon name="sticky" size={30} />
            </div>
            <div>
              <p className="text-sm font-semibold text-ink-200">لسه مفيش بوردات</p>
              <p className="mt-1 text-xs text-ink-400">اعمل بورد جديد وابدأ ارسم على طول</p>
            </div>
            <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
              ابدأ بورد جديد
            </Button>
          </div>
        )}

        {boards && boards.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {boards.map((b) => (
              <article
                key={b.id}
                className="group relative overflow-hidden rounded-2xl border border-ink-800 bg-ink-900 transition-all duration-200 hover:-translate-y-0.5 hover:border-ink-600 hover:shadow-xl hover:shadow-black/40"
              >
                <button
                  type="button"
                  onClick={() => onOpen(b.id)}
                  className="block w-full text-start"
                  aria-label={`افتح ${b.name}`}
                >
                  <div
                    className="relative h-32 w-full overflow-hidden bg-ink-850"
                    style={{ backgroundColor: `${b.color}14` }}
                  >
                    <span className="absolute inset-x-0 top-0 h-1" style={{ backgroundColor: b.color }} />
                    {b.has_thumb ? (
                      <img
                        src={`/api/boards/${b.id}/thumb?${b.version}`}
                        alt=""
                        loading="lazy"
                        className="h-full w-full object-cover opacity-90"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center">
                        <Icon name="grid" size={34} className="text-ink-700" />
                      </div>
                    )}
                  </div>
                  <div className="p-3.5">
                    <h2 className="truncate text-sm font-semibold text-ink-200">{b.name}</h2>
                    <p className="mt-1 text-[11px] text-ink-400">
                      {b.object_count} عنصر · {relativeTime(b.updated_at)}
                    </p>
                  </div>
                </button>

                <div className="absolute end-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <IconButton
                    icon="share"
                    label="رابط مشاركة"
                    size="sm"
                    onClick={() => void share(b)}
                    className="bg-ink-900/85"
                  />
                  <IconButton
                    icon="pen"
                    label="إعادة تسمية"
                    size="sm"
                    onClick={() => {
                      setRenaming(b);
                      setRenameValue(b.name);
                    }}
                    className="bg-ink-900/85"
                  />
                  <IconButton
                    icon="trash"
                    label="حذف"
                    size="sm"
                    danger
                    onClick={() => setDeleting(b)}
                    className="bg-ink-900/85"
                  />
                </div>

                {b.share_token && (
                  <span className="absolute bottom-3 end-3 rounded-full bg-mint-400/15 px-2 py-0.5 text-[10px] text-mint-400">
                    متشارك
                  </span>
                )}
              </article>
            ))}
          </div>
        )}
      </div>

      <Modal open={creating} onClose={() => setCreating(false)} title="بورد جديد">
        <label className="mb-1 block text-[11px] text-ink-400" htmlFor="board-name">
          الاسم
        </label>
        <input
          id="board-name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void create()}
          placeholder="مثلاً: أفكار المنتج"
          autoFocus
          className="mb-4 w-full rounded-xl border border-ink-700 bg-ink-850 px-3 py-2.5 text-sm text-ink-200 outline-none focus:border-brand-500"
        />
        <p className="mb-2 text-[11px] text-ink-400">اللون</p>
        <div className="mb-5 flex flex-wrap gap-2">
          {PALETTE.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setNewColor(c)}
              aria-label={`لون ${c}`}
              className={`h-8 w-8 rounded-lg transition-transform hover:scale-110 ${
                newColor === c ? 'ring-2 ring-white/80 ring-offset-2 ring-offset-ink-900' : ''
              }`}
              style={{ backgroundColor: c }}
            />
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => void create()} disabled={busy} className="flex-1">
            {busy ? 'بيتعمل…' : 'إنشاء وفتح'}
          </Button>
          <Button variant="soft" onClick={() => setCreating(false)}>
            إلغاء
          </Button>
        </div>
      </Modal>

      <Modal open={!!renaming} onClose={() => setRenaming(null)} title="إعادة تسمية">
        <input
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void rename()}
          autoFocus
          className="mb-4 w-full rounded-xl border border-ink-700 bg-ink-850 px-3 py-2.5 text-sm text-ink-200 outline-none focus:border-brand-500"
          aria-label="الاسم الجديد"
        />
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => void rename()} className="flex-1">
            حفظ
          </Button>
          <Button variant="soft" onClick={() => setRenaming(null)}>
            إلغاء
          </Button>
        </div>
      </Modal>

      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="حذف البورد">
        <p className="mb-4 text-sm text-ink-300">
          متأكد إنك عايز تحذف «{deleting?.name}»؟ الحذف نهائي.
        </p>
        <div className="flex gap-2">
          <Button variant="danger" onClick={() => void remove()} className="flex-1">
            احذف
          </Button>
          <Button variant="soft" onClick={() => setDeleting(null)} className="flex-1">
            إلغاء
          </Button>
        </div>
      </Modal>

      {toast && <Toast message={toast} />}
    </div>
  );
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const diff = Math.max(0, Date.now() - then);
  const min = Math.floor(diff / 60_000);
  if (min < 1) return 'دلوقتي';
  if (min < 60) return `قبل ${min} دقيقة`;
  const hours = Math.floor(min / 60);
  if (hours < 24) return `قبل ${hours} ساعة`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `قبل ${days} يوم`;
  return new Date(iso).toLocaleDateString('ar-EG', { day: 'numeric', month: 'short' });
}
