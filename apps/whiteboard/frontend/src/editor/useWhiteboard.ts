/** React binding for WhiteboardEngine: owns the instance, mirrors its state. */

import { useCallback, useEffect, useRef, useState } from 'react';
import { EMPTY_SELECTION, WhiteboardEngine, type LoadReport, type SelectionInfo } from './engine';
import type { SceneDoc, StyleState, Tool } from '../types';

export const DEFAULT_STYLE: StyleState = {
  stroke: '#f8fafc',
  fill: '#6366f1',
  filled: false,
  strokeWidth: 3,
  opacity: 1,
  fontSize: 24,
};

export type WhiteboardApi = {
  hostRef: (el: HTMLDivElement | null) => void;
  ready: boolean;
  tool: Tool;
  setTool: (t: Tool) => void;
  style: StyleState;
  setStyle: (patch: Partial<StyleState>) => void;
  selection: SelectionInfo;
  zoom: number;
  canUndo: boolean;
  canRedo: boolean;
  undo: () => void;
  redo: () => void;
  zoomBy: (factor: number) => void;
  zoomTo: (zoom: number) => void;
  resetView: () => void;
  fitToContent: () => void;
  clear: () => void;
  /** Force-load a scene document (used by the live-sync poller). */
  reload: (doc: SceneDoc) => Promise<void>;
  deleteSelection: () => void;
  duplicate: () => void;
  copyAsImage: () => Promise<void>;
  exportPNG: () => void;
  addImage: (file: File) => Promise<void>;
  engine: () => WhiteboardEngine | null;
};

export function useWhiteboard({
  doc,
  docKey,
  readOnly = false,
  onDirty,
  onLoadIssue,
}: {
  doc: SceneDoc | null;
  docKey: string;
  readOnly?: boolean;
  onDirty: () => void;
  /** Called when a board could not be restored 1:1 (dropped/un-enlivenable objects). */
  onLoadIssue?: (report: LoadReport) => void;
}): WhiteboardApi {
  // Callback ref → state, so the engine effect re-runs when the host mounts
  // (the editor renders a spinner first, then the canvas shell).
  const [hostEl, setHostEl] = useState<HTMLDivElement | null>(null);
  const hostRef = useCallback((el: HTMLDivElement | null) => setHostEl(el), []);
  const engineRef = useRef<WhiteboardEngine | null>(null);
  const dirtyCb = useRef(onDirty);
  dirtyCb.current = onDirty;

  const [ready, setReady] = useState(false);
  const [tool, setToolState] = useState<Tool>('select');
  const [style, setStyleState] = useState<StyleState>(DEFAULT_STYLE);
  const [selection, setSelection] = useState<SelectionInfo>(EMPTY_SELECTION);
  const [zoom, setZoom] = useState(1);
  const [history, setHistory] = useState({ undo: false, redo: false });
  // What the canvas currently mirrors. Fixed-keyed on `docKey` alone, a null doc
  // that raced the engine (or a failed load) used to block the real payload for
  // good — the board then stayed empty until a manual reload.
  const loadedRef = useRef<{ key: string; doc: unknown } | null>(null);
  const issueCb = useRef(onLoadIssue);
  issueCb.current = onLoadIssue;

  // Create the engine once the host element exists.
  useEffect(() => {
    const host = hostEl;
    if (!host) return;
    let engine: WhiteboardEngine;
    const syncHistory = () =>
      setHistory({ undo: engine.canUndo(), redo: engine.canRedo() });
    engine = new WhiteboardEngine(host, {
      style: DEFAULT_STYLE,
      readOnly,
      callbacks: {
        onDirty: () => {
          dirtyCb.current();
          syncHistory();
        },
        onSelection: setSelection,
        onZoom: setZoom,
        onToolDone: () => setToolState(engine.getTool()),
        onToolChange: setToolState,
      },
    });
    engineRef.current = engine;
    setReady(true);
    return () => {
      engineRef.current = null;
      loadedRef.current = null;
      setReady(false);
      engine.dispose();
    };
  }, [hostEl, readOnly]);

  // (Re)load the scene whenever the open board changes.
  useEffect(() => {
    const engine = engineRef.current;
    if (!engine || !ready) return;

    const incoming = doc && Array.isArray(doc.objects) ? doc.objects.length : 0;
    const seen = loadedRef.current;
    if (seen && seen.key === docKey) {
      if (seen.doc === doc) return;
      // Same board, new payload: reload only when the canvas is still empty
      // (the first pass had no doc yet, or the load failed) — never wipe edits.
      if (!(engine.canvas.getObjects().length === 0 && incoming > 0)) return;
    }
    loadedRef.current = { key: docKey, doc };

    void engine
      .load(doc)
      .then((report) => {
        if (report.error || report.dropped.length > 0) issueCb.current?.(report);
        // fit against what is actually on the canvas, not what the doc claimed.
        if (engine.canvas.getObjects().length > 0) engine.fitToContent(1);
        setHistory({ undo: engine.canUndo(), redo: engine.canRedo() });
        setZoom(engine.canvas.getZoom());
      })
      .catch((err: unknown) => {
        issueCb.current?.({
          expected: incoming,
          loaded: engine.canvas.getObjects().length,
          dropped: [],
          repaired: 0,
          source: 'invalid',
          salvaged: false,
          error: err instanceof Error ? err.message : String(err),
        });
      });
  }, [doc, docKey, ready]);

  const withEngine = useCallback(<T,>(fn: (e: WhiteboardEngine) => T): T | undefined => {
    const engine = engineRef.current;
    return engine ? fn(engine) : undefined;
  }, []);

  const setTool = useCallback((t: Tool) => {
    withEngine((e) => e.setTool(t));
  }, [withEngine]);

  const setStyle = useCallback((patch: Partial<StyleState>) => {
    setStyleState((prev) => ({ ...prev, ...patch }));
    withEngine((e) => e.setStyle(patch));
  }, [withEngine]);

  const exportPNG = useCallback(() => {
    withEngine((e) => {
      const url = e.exportPNG(2);
      const a = document.createElement('a');
      a.href = url;
      a.download = `whiteboard-${new Date().toISOString().slice(0, 10)}.png`;
      a.click();
    });
  }, [withEngine]);

  const addImage = useCallback(
    async (file: File) => {
      const engine = engineRef.current;
      if (engine) await engine.addImageFile(file);
    },
    [],
  );

  const copyAsImage = useCallback(async () => {
    const engine = engineRef.current;
    if (engine) await engine.copyAsImage();
  }, []);

  /** Force-load a document (live sync / conflict reload). */
  const reload = useCallback(
    async (next: SceneDoc) => {
      const engine = engineRef.current;
      if (!engine) return;
      loadedRef.current = { key: docKey, doc: next };
      const report = await engine.load(next);
      if (report.error || report.dropped.length > 0) issueCb.current?.(report);
      if (engine.canvas.getObjects().length > 0) engine.fitToContent(1);
      setHistory({ undo: engine.canUndo(), redo: engine.canRedo() });
      setZoom(engine.canvas.getZoom());
      setSelection(EMPTY_SELECTION);
    },
    [docKey],
  );

  return {
    hostRef,
    ready,
    tool,
    setTool,
    style,
    setStyle,
    selection,
    zoom,
    canUndo: history.undo,
    canRedo: history.redo,
    undo: () => withEngine((e) => e.undo()),
    redo: () => withEngine((e) => e.redo()),
    zoomBy: (f: number) => withEngine((e) => e.zoomBy(f)),
    zoomTo: (z: number) => withEngine((e) => e.zoomTo(z)),
    resetView: () => withEngine((e) => e.resetView()),
    fitToContent: () => withEngine((e) => e.fitToContent()),
    clear: () => withEngine((e) => e.clear()),
    reload,
    deleteSelection: () => withEngine((e) => e.deleteSelection()),
    duplicate: () => withEngine((e) => void e.duplicate()),
    copyAsImage,
    exportPNG,
    addImage,
    engine: () => engineRef.current,
  };
}
