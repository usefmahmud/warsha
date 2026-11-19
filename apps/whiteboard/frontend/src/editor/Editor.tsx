/** The board editor screen: canvas + tools + autosave + share. */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, api } from '../api';
import { Icon } from '../components/Icons';
import { Button, Modal, Spinner, Toast } from '../components/ui';
import type { Board, SaveState, ShareInfo } from '../types';
import { StylePanel } from './StylePanel';
import { Toolbar } from './Toolbar';
import { TopBar } from './TopBar';
import { useWhiteboard } from './useWhiteboard';
import type { LoadReport } from './engine';

const AUTOSAVE_MS = 2000;
const POLL_MS = 3000;

export function Editor({
  boardId,
  onBack,
}: {
  boardId: string;
  onBack: () => void;
}) {
  const [board, setBoard] = useState<Board | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [grid, setGrid] = useState(() => localStorage.getItem('wb:grid') !== '0');
  const [share, setShare] = useState<ShareInfo | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [conflict, setConflict] = useState<Board | null>(null);
  const [showStyle, setShowStyle] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const versionRef = useRef(0);
  const dirtyRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const saveRef = useRef<() => void>(() => {});
  /** Set when a board could not be restored — saving then would overwrite the server copy. */
  const loadIssueRef = useRef<LoadReport | null>(null);

  /* ------------------------------------------------------------- load board */

  useEffect(() => {
    let alive = true;
    setBoard(null);
    setLoadError(null);
    loadIssueRef.current = null;
    api
      .getBoard(boardId)
      .then((b) => {
        if (!alive) return;
        versionRef.current = b.version;
        setBoard(b);
        if (b.share_token) setShare({ share_token: b.share_token, share_url: shareUrl(b.share_token) });
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setLoadError(e instanceof ApiError ? e.messageAr : 'حصل خطأ في تحميل البورد');
      });
    return () => {
      alive = false;
    };
  }, [boardId]);

  /* -------------------------------------------------------------- autosave */

  const flushSave = useCallback(
    async (opts: { force?: boolean } = {}) => {
      const engine = wbRef.current?.engine();
      if (!engine) return;
      if (!dirtyRef.current && !opts.force) return;
      if (loadIssueRef.current) {
        // Restoring the scene failed: a save here would replace the stored
        // document with the empty/partial canvas. Refuse and say why.
        setSaveState('error');
        setToast('البورد مااتحمّلش كامل — الحفظ متوقف عشان البورد الأصلي ما يتمسحش');
        return;
      }
      setSaveState('saving');
      try {
        const doc = engine.toDoc();
        const thumb = engine.thumbnail();
        const res = await api.patchBoard(boardId, {
          doc,
          ...(thumb ? { thumb } : {}),
          ...(opts.force ? {} : { version: versionRef.current }),
        });
        versionRef.current = res.version;
        dirtyRef.current = false;
        setSaveState('saved');
        setConflict(null);
      } catch (e) {
        if (e instanceof ApiError && e.isConflict) {
          setSaveState('conflict');
          setConflict(e.conflictBoard);
        } else {
          setSaveState('error');
          setToast(e instanceof ApiError ? e.messageAr : 'فشل الحفظ');
        }
      }
    },
    [boardId],
  );

  const wbRef = useRef<ReturnType<typeof useWhiteboard> | null>(null);

  const handleDirty = useCallback(() => {
    dirtyRef.current = true;
    setSaveState((s) => (s === 'conflict' ? s : 'dirty'));
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      saveRef.current();
    }, AUTOSAVE_MS);
  }, []);

  /** A board that did not come back 1:1 must be visible, not a blank canvas. */
  const handleLoadIssue = useCallback((report: LoadReport) => {
    const total = report.expected;
    const lost = total - report.loaded;
    loadIssueRef.current = report.loaded === 0 && total > 0 ? report : null;
    if (report.loaded === 0 && total > 0) {
      setToast(`البورد فيه ${total} عنصر وماحصلش تحميل — جرّب تحديث الصفحة`);
    } else if (lost > 0) {
      setToast(`اتحمّل ${report.loaded} من ${total} عنصر (${lost} عنصر تالف اتشال)`);
    } else if (report.error) {
      setToast(`تحذير تحميل: ${report.error}`);
    }
  }, []);

  const wb = useWhiteboard({
    doc: board?.doc ?? null,
    docKey: boardId,
    onDirty: handleDirty,
    onLoadIssue: handleLoadIssue,
  });
  wbRef.current = wb;

  useEffect(() => {
    saveRef.current = () => {
      void flushSave();
    };
  }, [flushSave]);

  /* ------------------------------------------------------------ live sync */

  const saveStateRef = useRef(saveState);
  saveStateRef.current = saveState;

  // SPEC: "lightweight live refresh via polling every 3s (v1)". Without this an open tab
  // never sees a doc written elsewhere (another tab, or a board seeded after the
  // tab was opened) — the canvas just looks empty/out of date with no error.
  useEffect(() => {
    if (!board) return;
    let alive = true;
    let busy = false;
    const tick = async () => {
      if (!alive || busy || document.visibilityState === 'hidden') return;
      busy = true;
      try {
        const fresh = await api.getBoard(boardId);
        if (!alive || fresh.version === versionRef.current) return;
        if (dirtyRef.current || saveStateRef.current === 'saving') {
          setToast('البورد اتعدّل من مكان تاني — احفظ شغلك أو افتح النسخة الجديدة');
          return;
        }
        versionRef.current = fresh.version;
        setBoard(fresh);
        await wbRef.current?.reload(fresh.doc);
        setSaveState('saved');
        setToast('اتحدّث البورد من مكان تاني');
      } catch {
        /* offline / transient — the next tick retries */
      } finally {
        busy = false;
      }
    };
    const timer = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [boardId, board]);

  // Save on tab hide / close so nothing is lost when the user just leaves.
  useEffect(() => {
    const onHide = () => {
      if (!dirtyRef.current) return;
      const engine = wbRef.current?.engine();
      if (!engine) return;
      const body = JSON.stringify({ doc: engine.toDoc(), version: versionRef.current });
      try {
        fetch(`/api/boards/${boardId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body,
          keepalive: true,
        });
        dirtyRef.current = false;
      } catch {
        /* best effort */
      }
    };
    window.addEventListener('pagehide', onHide);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') onHide();
    });
    return () => window.removeEventListener('pagehide', onHide);
  }, [boardId]);

  // Ctrl+S → immediate save
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        void flushSave({ force: true });
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [flushSave]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    localStorage.setItem('wb:grid', grid ? '1' : '0');
  }, [grid]);

  /* ------------------------------------------------------------- handlers */

  const rename = async (next: string) => {
    setBoard((b) => (b ? { ...b, name: next } : b));
    try {
      await api.patchBoard(boardId, { name: next });
    } catch {
      setToast('مش قادر أعدّل الاسم');
    }
  };

  const openShare = async () => {
    setShareOpen(true);
    try {
      const info = await api.share(boardId);
      setShare(info);
    } catch {
      setToast('مش قادر أعمل رابط مشاركة');
    }
  };

  const revokeShare = async () => {
    try {
      await api.unshare(boardId);
      setShare(null);
      setToast('اتلغى رابط المشاركة');
    } catch {
      setToast('مش قادر ألغي الرابط');
    }
  };

  const copyLink = async () => {
    if (!share) return;
    try {
      await navigator.clipboard.writeText(share.share_url);
      setToast('اتنسخ الرابط');
    } catch {
      setToast('انسخ الرابط من الحقل');
    }
  };

  const resolveConflict = (mode: 'reload' | 'overwrite') => {
    if (mode === 'reload' && conflict) {
      versionRef.current = conflict.version;
      setBoard(conflict);
      dirtyRef.current = false;
      setSaveState('saved');
      setConflict(null);
      window.location.reload();
      return;
    }
    setSaveState('saving');
    void flushSave({ force: true });
  };

  if (loadError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-sm text-rose-400">{loadError}</p>
        <Button onClick={onBack} icon="back" variant="soft">
          رجوع للبوردات
        </Button>
      </div>
    );
  }

  if (!board) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="بيجهّز البورد…" />
      </div>
    );
  }

  return (
    <div className="relative h-full w-full overflow-hidden bg-ink-950">
      <TopBar
        name={board.name}
        onRename={rename}
        saveState={saveState}
        canUndo={wb.canUndo}
        canRedo={wb.canRedo}
        onUndo={wb.undo}
        onRedo={wb.redo}
        zoom={wb.zoom}
        onZoomIn={() => wb.zoomBy(1.2)}
        onZoomOut={() => wb.zoomBy(1 / 1.2)}
        onResetZoom={wb.resetView}
        onFit={wb.fitToContent}
        grid={grid}
        onToggleGrid={() => setGrid((g) => !g)}
        onExport={() => {
          wb.exportPNG();
          setToast('اتصدّر PNG');
        }}
        onCopyImage={() => {
          void wb
            .copyAsImage()
            .then(() => setToast('اتنسخ كصورة'))
            .catch((e: Error) => setToast(e.message));
        }}
        onShare={openShare}
        onHelp={() => setHelpOpen(true)}
        onBack={onBack}
      />

      {/* workspace: tools rail | canvas | style panel — no overlay over the canvas */}
      <div className="absolute inset-x-0 bottom-0 top-14 flex">
        <Toolbar tool={wb.tool} onTool={wb.setTool} onImage={(f) => void wb.addImage(f)} />

        <div
          className={`relative min-w-0 flex-1 ${grid ? 'dot-grid' : ''} canvas-shell`}
          style={{ backgroundColor: '#0b0f19' }}
        >
          <div ref={wb.hostRef} className="h-full w-full touch-none pb-[60px] md:pb-0" />
        </div>

        <aside className="hidden w-[248px] shrink-0 overflow-y-auto border-s border-ink-800 bg-ink-900/60 p-2.5 md:block">
          <StylePanel
            style={wb.style}
            onChange={wb.setStyle}
            selection={wb.selection}
            onClear={() => setConfirmClear(true)}
          />
        </aside>
      </div>

      {/* mobile: style sheet */}
      <button
        type="button"
        onClick={() => setShowStyle((s) => !s)}
        className="absolute bottom-[74px] end-3 z-20 flex h-11 w-11 items-center justify-center rounded-full border border-ink-700 bg-ink-850/95 text-brand-400 shadow-lg backdrop-blur md:hidden"
        aria-label="إعدادات الرسم"
        aria-expanded={showStyle}
      >
        <Icon name="sparkle" size={20} />
      </button>

      {/* floating delete for the current selection */}
      {wb.selection.count > 0 && (
        <div className="absolute bottom-[76px] start-1/2 z-20 flex -translate-x-1/2 items-center gap-1 rounded-xl border border-ink-700 bg-ink-850/95 px-1.5 py-1 shadow-xl backdrop-blur md:bottom-6">
          <span className="px-2 text-[11px] text-ink-300">{wb.selection.count} محدد</span>
          <button
            type="button"
            onClick={wb.duplicate}
            className="rounded-lg p-1.5 text-ink-300 hover:bg-ink-700"
            title="تكرار (Ctrl+D)"
            aria-label="تكرار"
          >
            <Icon name="copy" size={16} />
          </button>
          <button
            type="button"
            onClick={wb.deleteSelection}
            className="rounded-lg p-1.5 text-rose-400 hover:bg-rose-500/15"
            title="حذف (Delete)"
            aria-label="حذف"
          >
            <Icon name="trash" size={16} />
          </button>
        </div>
      )}

      {showStyle && (
        <div className="absolute inset-x-2 bottom-[130px] z-30 md:hidden">
          <StylePanel
            compact
            style={wb.style}
            onChange={wb.setStyle}
            selection={wb.selection}
            onClear={() => setConfirmClear(true)}
          />
          <button
            type="button"
            onClick={() => setShowStyle(false)}
            className="mt-1.5 w-full rounded-xl border border-ink-700 bg-ink-850/95 py-2 text-[11px] text-ink-300"
          >
            إغلاق
          </button>
        </div>
      )}

      {/* dialogs */}
      <Modal open={shareOpen} onClose={() => setShareOpen(false)} title="مشاركة البورد">
        <p className="mb-3 text-xs leading-6 text-ink-300">
          أي حد معاه الرابط ده يقدر يشوف البورد للقراءة فقط — من غير ما يعدّل فيه.
        </p>
        {share ? (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={share.share_url}
                onFocus={(e) => e.currentTarget.select()}
                dir="ltr"
                className="min-w-0 flex-1 rounded-xl border border-ink-700 bg-ink-850 px-3 py-2 text-xs text-ink-200 outline-none"
                aria-label="رابط المشاركة"
              />
              <Button variant="primary" icon="link" onClick={() => void copyLink()}>
                نسخ
              </Button>
            </div>
            <div className="flex items-center justify-between gap-2">
              <a
                href={share.share_url}
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-brand-400 hover:underline"
              >
                افتح المعاينة
              </a>
              <Button variant="danger" onClick={() => void revokeShare()}>
                إلغاء الرابط
              </Button>
            </div>
          </div>
        ) : (
          <Spinner label="بيجهّز الرابط…" />
        )}
      </Modal>

      <Modal open={helpOpen} onClose={() => setHelpOpen(false)} title="الاختصارات">
        <ul className="grid grid-cols-1 gap-2 text-xs text-ink-300 sm:grid-cols-2">
          {[
            ['V', 'تحديد'],
            ['P', 'قلم'],
            ['E', 'ممحاة'],
            ['R', 'مستطيل'],
            ['O', 'دائرة'],
            ['A', 'سهم'],
            ['T', 'نص'],
            ['N', 'ملاحظة لاصقة'],
            ['H', 'يد (تحريك)'],
            ['Ctrl + Z', 'تراجع'],
            ['Ctrl + Shift + Z', 'إعادة'],
            ['Ctrl + D', 'تكرار'],
            ['Ctrl + C / V', 'نسخ / لصق'],
            ['Delete', 'حذف'],
            ['Space + سحب', 'تحريك اللوحة'],
            ['Ctrl + S', 'حفظ فوري'],
            ['عجلة الماوس', 'تكبير / تصغير'],
          ].map(([k, v]) => (
            <li key={k} className="flex items-center justify-between gap-2 rounded-lg bg-ink-850 px-2.5 py-1.5">
              <span>{v}</span>
              <kbd className="ltr rounded bg-ink-800 px-1.5 py-0.5 text-[10px] text-ink-300">{k}</kbd>
            </li>
          ))}
        </ul>
      </Modal>

      <Modal open={confirmClear} onClose={() => setConfirmClear(false)} title="مسح البورد">
        <p className="mb-4 text-xs leading-6 text-ink-300">
          هيتشال كل العناصر من البورد. تقدر ترجعهم بـ Ctrl+Z.
        </p>
        <div className="flex gap-2">
          <Button
            variant="danger"
            className="flex-1"
            onClick={() => {
              wb.clear();
              setConfirmClear(false);
              setShowStyle(false);
            }}
          >
            امسح الكل
          </Button>
          <Button variant="soft" className="flex-1" onClick={() => setConfirmClear(false)}>
            إلغاء
          </Button>
        </div>
      </Modal>

      <Modal open={!!conflict} onClose={() => setConflict(null)} title="تعارض في الحفظ">
        <p className="mb-4 text-xs leading-6 text-ink-300">
          البورد ده اتعدّل من مكان تاني بعد ما فتحته. تحب تحمّل نسخة السيرفر ولا تكتب نسختك فوقها؟
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button variant="primary" onClick={() => resolveConflict('reload')} className="flex-1">
            تحميل نسخة السيرفر
          </Button>
          <Button variant="danger" onClick={() => resolveConflict('overwrite')} className="flex-1">
            حفظ نسختي
          </Button>
        </div>
      </Modal>

      {toast && <Toast message={toast} />}
    </div>
  );
}

export function shareUrl(token: string) {
  return `${window.location.origin}/#/s/${token}`;
}
