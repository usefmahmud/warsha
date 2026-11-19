/** Small shared UI atoms: buttons, modal sheet, toast, spinner. */

import { useEffect, type ReactNode } from 'react';
import { Icon, type IconName } from './Icons';

export function IconButton({
  icon,
  label,
  onClick,
  active = false,
  disabled = false,
  danger = false,
  size = 'md',
  title,
  className = '',
}: {
  icon: IconName;
  label?: string;
  onClick?: () => void;
  active?: boolean;
  disabled?: boolean;
  danger?: boolean;
  size?: 'sm' | 'md' | 'lg';
  title?: string;
  className?: string;
}) {
  const dims = size === 'sm' ? 'h-8 w-8' : size === 'lg' ? 'h-12 w-12' : 'h-10 w-10';
  const tone = danger
    ? 'text-rose-400 hover:bg-rose-500/15'
    : active
      ? 'bg-brand-500/20 text-brand-400 ring-1 ring-brand-500/40'
      : 'text-ink-300 hover:bg-ink-700/60 hover:text-ink-200';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title ?? label}
      aria-label={label ?? title}
      aria-pressed={active}
      className={`inline-flex ${dims} shrink-0 items-center justify-center rounded-xl transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-35 ${tone} ${className}`}
    >
      <Icon name={icon} size={size === 'sm' ? 16 : size === 'lg' ? 24 : 20} />
    </button>
  );
}

export function Button({
  children,
  onClick,
  variant = 'ghost',
  icon,
  disabled = false,
  className = '',
  type = 'button',
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'ghost' | 'danger' | 'soft';
  icon?: IconName;
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit';
}) {
  const variants = {
    primary:
      'bg-gradient-to-l from-brand-600 to-brand-400 text-white shadow-lg shadow-brand-600/25 hover:brightness-110',
    ghost: 'text-ink-200 hover:bg-ink-700/60 border border-ink-600/70',
    soft: 'bg-ink-850 text-ink-200 hover:bg-ink-800 border border-ink-700',
    danger: 'bg-rose-500/15 text-rose-400 hover:bg-rose-500/25 border border-rose-500/30',
  } as const;
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-40 ${variants[variant]} ${className}`}
    >
      {icon && <Icon name={icon} size={17} />}
      {children}
    </button>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  width = 'max-w-md',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className={`fade-in w-full ${width} rounded-t-3xl border border-ink-700 bg-ink-900 p-5 shadow-2xl sm:rounded-2xl`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink-200">{title}</h2>
          <IconButton icon="close" label="إغلاق" onClick={onClose} size="sm" />
        </div>
        {children}
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10 text-sm text-ink-300">
      <Icon name="spinner" size={22} className="animate-spin text-brand-400" />
      {label ?? 'بيحمّل…'}
    </div>
  );
}

export function Toast({ message, tone = 'info' }: { message: string; tone?: 'info' | 'error' }) {
  return (
    <div
      className={`fade-in pointer-events-none fixed bottom-24 left-1/2 z-50 -translate-x-1/2 rounded-xl border px-4 py-2.5 text-sm shadow-xl backdrop-blur sm:bottom-8 ${
        tone === 'error'
          ? 'border-rose-500/40 bg-rose-500/15 text-rose-300'
          : 'border-ink-600 bg-ink-850/95 text-ink-200'
      }`}
      role="status"
    >
      {message}
    </div>
  );
}
