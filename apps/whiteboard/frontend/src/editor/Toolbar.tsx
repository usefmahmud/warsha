/** Tool rail — vertical on desktop (RTL start side), scrollable bar on mobile. */

import { useRef } from 'react';
import { Icon, type IconName } from '../components/Icons';
import type { Tool } from '../types';

type ToolDef = { id: Tool; icon: IconName; label: string; key: string };

const TOOLS: ToolDef[] = [
  { id: 'select', icon: 'select', label: 'تحديد', key: 'V' },
  { id: 'pen', icon: 'pen', label: 'قلم', key: 'P' },
  { id: 'eraser', icon: 'eraser', label: 'ممحاة', key: 'E' },
  { id: 'rect', icon: 'rect', label: 'مستطيل', key: 'R' },
  { id: 'circle', icon: 'circle', label: 'دائرة', key: 'O' },
  { id: 'triangle', icon: 'triangle', label: 'مثلث', key: 'G' },
  { id: 'arrow', icon: 'arrow', label: 'سهم', key: 'A' },
  { id: 'text', icon: 'text', label: 'نص', key: 'T' },
  { id: 'sticky', icon: 'sticky', label: 'ملاحظة', key: 'N' },
  { id: 'hand', icon: 'hand', label: 'يد', key: 'H' },
];

export function Toolbar({
  tool,
  onTool,
  onImage,
}: {
  tool: Tool;
  onTool: (t: Tool) => void;
  onImage: (file: File) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onImage(file);
          e.target.value = '';
        }}
      />

      {/* desktop: vertical rail inside the flex layout (no canvas overlap) */}
      <div className="hidden h-full w-14 shrink-0 flex-col items-center gap-1 overflow-y-auto border-s border-ink-800 bg-ink-900/70 py-2 md:flex">
        {TOOLS.map((t) => (
          <ToolButton key={t.id} def={t} active={tool === t.id} onClick={() => onTool(t.id)} />
        ))}
        <div className="my-0.5 h-px w-7 bg-ink-700" />
        <ToolButton
          def={{ id: 'image', icon: 'image', label: 'صورة', key: '' }}
          active={false}
          onClick={() => fileRef.current?.click()}
        />
      </div>

      {/* mobile: bottom bar */}
      <div className="absolute inset-x-0 bottom-0 z-20 border-t border-ink-700/80 bg-ink-900/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden">
        <div className="no-scrollbar flex items-center gap-1 overflow-x-auto px-2 py-2">
          {TOOLS.map((t) => (
            <ToolButton key={t.id} def={t} active={tool === t.id} onClick={() => onTool(t.id)} compact />
          ))}
          <ToolButton
            def={{ id: 'image', icon: 'image', label: 'صورة', key: '' }}
            active={false}
            onClick={() => fileRef.current?.click()}
            compact
          />
        </div>
      </div>
    </>
  );
}

function ToolButton({
  def,
  active,
  onClick,
  compact = false,
}: {
  def: ToolDef;
  active: boolean;
  onClick: () => void;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={`${def.label}${def.key ? ` (${def.key})` : ''}`}
      aria-label={def.label}
      aria-pressed={active}
      className={`group relative flex shrink-0 items-center justify-center rounded-xl transition-all duration-150 ${
        compact ? 'h-11 w-11' : 'h-10 w-10'
      } ${
        active
          ? 'bg-gradient-to-br from-brand-500 to-brand-600 text-white shadow-lg shadow-brand-600/30'
          : 'text-ink-300 hover:bg-ink-700/70 hover:text-ink-200'
      }`}
    >
      <Icon name={def.icon} size={compact ? 21 : 19} />
      {!compact && def.key && (
        <span className="pointer-events-none absolute -end-1 -top-1 hidden rounded bg-ink-800 px-1 text-[9px] font-semibold text-ink-400 group-hover:block">
          {def.key}
        </span>
      )}
    </button>
  );
}
