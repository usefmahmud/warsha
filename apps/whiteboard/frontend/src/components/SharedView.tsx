/** Read-only board view behind a share link (`#/s/<token>`). */

import { useEffect, useState } from 'react';
import { ApiError, api } from '../api';
import { Button, Spinner } from '../components/ui';
import type { Board } from '../types';
import { useWhiteboard } from '../editor/useWhiteboard';
import { TopBar } from '../editor/TopBar';

export function SharedView({ token }: { token: string }) {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [grid, setGrid] = useState(true);

  const wb = useWhiteboard({
    doc: board?.doc ?? null,
    docKey: `shared-${token}`,
    readOnly: true,
    onDirty: () => undefined,
  });

  useEffect(() => {
    let alive = true;
    api
      .getShared(token)
      .then((b) => alive && setBoard(b))
      .catch((e: unknown) => {
        if (!alive) return;
        setError(e instanceof ApiError ? 'رابط المشاركة غير صالح أو اتلغى' : 'حصل خطأ');
      });
    return () => {
      alive = false;
    };
  }, [token]);

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-sm text-rose-400">{error}</p>
        <Button variant="soft" onClick={() => (window.location.hash = '#/')}>
          رجوع للرئيسية
        </Button>
      </div>
    );
  }

  if (!board) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="بيفتح البورد…" />
      </div>
    );
  }

  return (
    <div className="relative h-full w-full overflow-hidden bg-ink-950">
      <TopBar
        name={board.name}
        saveState="idle"
        canUndo={false}
        canRedo={false}
        onUndo={() => undefined}
        onRedo={() => undefined}
        zoom={wb.zoom}
        onZoomIn={() => wb.zoomBy(1.2)}
        onZoomOut={() => wb.zoomBy(1 / 1.2)}
        onResetZoom={wb.resetView}
        onFit={wb.fitToContent}
        grid={grid}
        onToggleGrid={() => setGrid((g) => !g)}
        onExport={wb.exportPNG}
        onBack={() => (window.location.hash = '#/')}
        readOnly
      />

      <div className="pointer-events-none absolute inset-x-0 top-14 z-20 flex justify-center">
        <span className="mt-3 rounded-full border border-mint-400/30 bg-mint-400/10 px-3 py-1 text-[11px] text-mint-400 backdrop-blur">
          عرض للقراءة فقط
        </span>
      </div>

      <div
        className={`absolute inset-x-0 bottom-0 top-14 canvas-shell ${grid ? 'dot-grid' : ''}`}
        style={{ backgroundColor: '#0b0f19' }}
      >
        <div ref={wb.hostRef} className="h-full w-full touch-none" />
      </div>
    </div>
  );
}
