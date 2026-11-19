/** Style panel: colours, stroke width, opacity, fill and font size. */

import { Icon } from '../components/Icons';
import { PALETTE, STICKY_COLORS, type StyleState } from '../types';
import type { SelectionInfo } from './engine';

export function StylePanel({
  style,
  onChange,
  selection,
  compact = false,
  onClear,
}: {
  style: StyleState;
  onChange: (patch: Partial<StyleState>) => void;
  selection: SelectionInfo;
  compact?: boolean;
  onClear?: () => void;
}) {
  const swatch = (color: string, active: boolean, onClick: () => void, size = 'h-7 w-7') => (
    <button
      key={color}
      type="button"
      onClick={onClick}
      aria-label={`لون ${color}`}
      className={`${size} shrink-0 rounded-lg transition-transform duration-150 hover:scale-110 ${
        active ? 'ring-2 ring-brand-400 ring-offset-2 ring-offset-ink-850' : 'ring-1 ring-white/10'
      }`}
      style={{ backgroundColor: color }}
    />
  );

  return (
    <div
      className={`pointer-events-auto flex flex-col gap-3.5 rounded-2xl border border-ink-700/80 bg-ink-850/92 p-3 shadow-xl shadow-black/40 backdrop-blur-md ${
        compact ? 'w-full' : 'w-[236px]'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold tracking-wide text-ink-400">الألوان</span>
        <span className="text-[10px] text-ink-400">
          {selection.count > 0 ? `${selection.count} محدد` : 'افتراضي'}
        </span>
      </div>

      <div className="grid grid-cols-7 gap-1.5">
        {PALETTE.map((c) => swatch(c, style.stroke === c, () => onChange({ stroke: c })))}
      </div>

      <label className="flex items-center justify-between gap-2 text-[11px] text-ink-300">
        <span>السماكة</span>
        <span className="ltr text-ink-400">{style.strokeWidth}px</span>
      </label>
      <input
        type="range"
        min={1}
        max={24}
        step={1}
        value={style.strokeWidth}
        onChange={(e) => onChange({ strokeWidth: Number(e.target.value) })}
        aria-label="سماكة الخط"
      />

      <label className="flex items-center justify-between gap-2 text-[11px] text-ink-300">
        <span>الشفافية</span>
        <span className="ltr text-ink-400">{Math.round(style.opacity * 100)}%</span>
      </label>
      <input
        type="range"
        min={10}
        max={100}
        step={5}
        value={Math.round(style.opacity * 100)}
        onChange={(e) => onChange({ opacity: Number(e.target.value) / 100 })}
        aria-label="الشفافية"
      />

      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] text-ink-300">تعبئة الشكل</span>
        <button
          type="button"
          role="switch"
          aria-checked={style.filled}
          onClick={() => onChange({ filled: !style.filled })}
          className={`relative h-6 w-11 rounded-full transition-colors duration-200 ${
            style.filled ? 'bg-brand-500' : 'bg-ink-700'
          }`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all duration-200 ${
              style.filled ? 'start-[22px]' : 'start-0.5'
            }`}
          />
        </button>
      </div>

      {style.filled && (
        <div className="grid grid-cols-7 gap-1.5">
          {PALETTE.map((c) => swatch(c, style.fill === c, () => onChange({ fill: c }), 'h-6 w-6'))}
        </div>
      )}

      <div className="flex items-center justify-between gap-2 text-[11px] text-ink-300">
        <span>حجم الخط</span>
        <span className="ltr text-ink-400">{style.fontSize}</span>
      </div>
      <div className="flex gap-1.5">
        {[16, 24, 36, 56].map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onChange({ fontSize: s })}
            className={`ltr flex-1 rounded-lg py-1 text-[11px] transition-colors ${
              style.fontSize === s
                ? 'bg-brand-500/20 text-brand-400 ring-1 ring-brand-500/40'
                : 'bg-ink-800 text-ink-300 hover:bg-ink-700'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="border-t border-ink-700/70 pt-2.5">
        <span className="mb-1.5 block text-[11px] font-semibold tracking-wide text-ink-400">
          ألوان الملاحظات
        </span>
        <div className="grid grid-cols-6 gap-1.5">
          {STICKY_COLORS.map((c) => swatch(c, false, () => onChange({ fill: c }), 'h-6 w-6'))}
        </div>
      </div>

      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="mt-0.5 flex items-center justify-center gap-1.5 rounded-lg border border-rose-500/25 py-1.5 text-[11px] text-rose-400 transition-colors hover:bg-rose-500/10"
        >
          <Icon name="trash" size={13} />
          مسح البورد (قابل للتراجع)
        </button>
      )}
    </div>
  );
}
