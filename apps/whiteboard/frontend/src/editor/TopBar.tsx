/** Editor top bar: name, save status, history, zoom, export/share actions. */

import { useEffect, useRef, useState } from 'react';
import { Icon } from '../components/Icons';
import { IconButton } from '../components/ui';
import type { SaveState } from '../types';

const SAVE_LABEL: Record<SaveState, { text: string; tone: string; dot: string }> = {
  idle: { text: 'جاهز', tone: 'text-ink-400', dot: 'bg-ink-400' },
  dirty: { text: 'تعديلات مش محفوظة', tone: 'text-amber-300', dot: 'bg-amber-300' },
  saving: { text: 'بيتحفظ…', tone: 'text-brand-400', dot: 'bg-brand-400 animate-pulse' },
  saved: { text: 'اتحفظ', tone: 'text-mint-400', dot: 'bg-mint-400' },
  error: { text: 'فشل الحفظ', tone: 'text-rose-400', dot: 'bg-rose-400' },
  conflict: { text: 'تعارض في الحفظ', tone: 'text-rose-400', dot: 'bg-rose-400 animate-pulse' },
};

export function SaveBadge({ state }: { state: SaveState }) {
  const s = SAVE_LABEL[state];
  return (
    <div className={`flex items-center gap-1.5 text-[11px] font-medium ${s.tone}`} role="status">
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      <span className="hidden sm:inline">{s.text}</span>
    </div>
  );
}

export function TopBar({
  name,
  onRename,
  saveState,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  zoom,
  onZoomIn,
  onZoomOut,
  onResetZoom,
  onFit,
  grid,
  onToggleGrid,
  onExport,
  onCopyImage,
  onShare,
  onHelp,
  onBack,
  readOnly = false,
}: {
  name: string;
  onRename?: (next: string) => void;
  saveState: SaveState;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetZoom: () => void;
  onFit: () => void;
  grid: boolean;
  onToggleGrid: () => void;
  onExport?: () => void;
  onCopyImage?: () => void;
  onShare?: () => void;
  onHelp?: () => void;
  onBack?: () => void;
  readOnly?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => setDraft(name), [name]);
  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const commit = () => {
    setEditing(false);
    const next = draft.trim();
    if (next && next !== name) onRename?.(next);
    else setDraft(name);
  };

  return (
    <header className="pointer-events-auto absolute inset-x-0 top-0 z-30 flex h-14 items-center gap-2 border-b border-ink-800/80 bg-ink-900/85 px-2 backdrop-blur-md sm:px-3">
      {onBack && <IconButton icon="back" label="رجوع للبوردات" onClick={onBack} size="sm" />}

      <div className="flex min-w-0 flex-1 items-center gap-2">
        {editing && onRename ? (
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commit();
              if (e.key === 'Escape') {
                setDraft(name);
                setEditing(false);
              }
            }}
            className="w-full max-w-[220px] rounded-lg border border-brand-500/60 bg-ink-850 px-2 py-1 text-sm text-ink-200 outline-none"
            aria-label="اسم البورد"
            autoFocus
          />
        ) : (
          <button
            type="button"
            onClick={() => onRename && setEditing(true)}
            className="group flex min-w-0 items-center gap-1.5 truncate rounded-lg px-1.5 py-1 text-sm font-semibold text-ink-200 transition-colors hover:bg-ink-800"
            title={onRename ? 'اضغط لإعادة التسمية' : name}
          >
            <span className="truncate">{name || 'بورد'}</span>
            {onRename && (
              <Icon
                name="pen"
                size={12}
                className="shrink-0 text-ink-400 opacity-0 transition-opacity group-hover:opacity-100"
              />
            )}
          </button>
        )}
        {!readOnly && <SaveBadge state={saveState} />}
      </div>

      <div className="flex items-center gap-0.5">
        {!readOnly && (
          <>
            <IconButton icon="undo" label="تراجع (Ctrl+Z)" onClick={onUndo} disabled={!canUndo} size="sm" />
            <IconButton
              icon="redo"
              label="إعادة (Ctrl+Shift+Z)"
              onClick={onRedo}
              disabled={!canRedo}
              size="sm"
            />
            <div className="mx-1 hidden h-6 w-px bg-ink-700 sm:block" />
          </>
        )}

        <div className="hidden items-center gap-0.5 rounded-xl bg-ink-850/70 px-1 sm:flex">
          <IconButton icon="zoomOut" label="تصغير" onClick={onZoomOut} size="sm" />
          <button
            type="button"
            onClick={onResetZoom}
            className="ltr min-w-11 rounded px-1 text-[11px] font-medium text-ink-300 hover:text-ink-200"
            title="إعادة الضبط 100%"
          >
            {Math.round(zoom * 100)}%
          </button>
          <IconButton icon="zoomIn" label="تكبير" onClick={onZoomIn} size="sm" />
          <IconButton icon="fit" label="ملاءمة المحتوى" onClick={onFit} size="sm" />
        </div>

        <IconButton
          icon="grid"
          label="نقط الخلفية"
          onClick={onToggleGrid}
          active={grid}
          size="sm"
        />
        {onExport && <IconButton icon="download" label="تصدير PNG" onClick={onExport} size="sm" />}
        {onCopyImage && (
          <IconButton icon="copy" label="نسخ كصورة" onClick={onCopyImage} size="sm" className="hidden sm:inline-flex" />
        )}
        {onShare && <IconButton icon="share" label="رابط المشاركة" onClick={onShare} size="sm" />}
        {onHelp && (
          <IconButton icon="help" label="الاختصارات" onClick={onHelp} size="sm" className="hidden sm:inline-flex" />
        )}
      </div>
    </header>
  );
}
