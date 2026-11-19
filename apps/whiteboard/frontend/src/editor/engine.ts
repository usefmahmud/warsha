/**
 * WhiteboardEngine — a thin, framework-free controller around Fabric.js v6.
 *
 * Responsibilities: tool state machine (pen / eraser / shapes / text / sticky /
 * pan), zoom & pan (wheel + pinch), selection ops (duplicate / delete / copy),
 * undo-redo history, and scene (de)serialization.
 *
 * React never touches fabric objects directly — it calls methods here and reads
 * state through the callbacks, which keeps the canvas imperative and fast.
 */

import {
  ActiveSelection,
  Canvas,
  Circle,
  Group,
  IText,
  Line,
  PencilBrush,
  Point,
  Rect,
  Shadow,
  Textbox,
  Triangle,
  FabricImage,
  util,
  type FabricObject,
  type TPointerEvent,
  type TPointerEventInfo,
} from 'fabric';

import { normalizeDoc, type DroppedObject } from './normalize';
import type { SceneDoc, StyleState, Tool } from '../types';

export type SelectionInfo = {
  count: number;
  fill: string | null;
  stroke: string | null;
  strokeWidth: number | null;
  opacity: number | null;
};

/** Diagnostics for one `load()` call — verified, never assumed. */
export type LoadReport = {
  /** Objects the stored document claimed to hold. */
  expected: number;
  /** Objects actually present on the canvas afterwards. */
  loaded: number;
  dropped: DroppedObject[];
  repaired: number;
  source: 'ok' | 'json-string' | 'invalid';
  /** True when the per-object fallback had to run. */
  salvaged: boolean;
  error: string | null;
};

export type EngineCallbacks = {
  /** The scene changed in a way that must be persisted. */
  onDirty: () => void;
  onSelection: (info: SelectionInfo) => void;
  onZoom: (zoom: number) => void;
  /** A one-shot tool finished (e.g. text placed) — UI should fall back to select. */
  onToolDone: () => void;
  onToolChange: (tool: Tool) => void;
};

const MIN_ZOOM = 0.15;
const MAX_ZOOM = 6;
const HISTORY_LIMIT = 60;
const SHAPE_MIN = 4;
const STICKY_DEFAULT = 'اكتب هنا…';

export const EMPTY_SELECTION: SelectionInfo = {
  count: 0,
  fill: null,
  stroke: null,
  strokeWidth: null,
  opacity: null,
};

const SHAPE_TOOLS: Tool[] = ['rect', 'circle', 'triangle', 'arrow'];

export class WhiteboardEngine {
  readonly canvas: Canvas;
  private host: HTMLElement;
  private cb: EngineCallbacks;
  private tool: Tool = 'select';
  private style: StyleState;
  private readOnly: boolean;

  private history: string[] = [];
  private historyIndex = -1;
  private loading = false;
  private drawing = false;
  private erasing = false;
  private spaceDown = false;

  private start: Point | null = null;
  private draft: FabricObject | null = null;
  private panFrom: { x: number; y: number; tx: number; ty: number } | null = null;
  private clipboard: FabricObject[] = [];
  private pinch: { dist: number; zoom: number; mid: Point } | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private disposed = false;
  private touchHandlers: Array<[string, EventListener]> = [];

  constructor(host: HTMLElement, opts: {
    style: StyleState;
    readOnly?: boolean;
    callbacks: EngineCallbacks;
  }) {
    this.host = host;
    this.cb = opts.callbacks;
    this.style = { ...opts.style };
    this.readOnly = opts.readOnly ?? false;

    const canvasEl = document.createElement('canvas');
    host.appendChild(canvasEl);

    this.canvas = new Canvas(canvasEl, {
      width: host.clientWidth || 800,
      height: host.clientHeight || 600,
      backgroundColor: 'transparent',
      preserveObjectStacking: true,
      selection: true,
      selectionColor: 'rgba(99,102,241,0.12)',
      selectionBorderColor: '#6366f1',
      selectionLineWidth: 1.5,
      controlsAboveOverlay: true,
      stopContextMenu: true,
      fireRightClick: false,
      uniformScaling: false,
    });

    // Debug handle: lets E2E checks and the console inspect the live scene.
    (window as unknown as { __wb?: WhiteboardEngine }).__wb = this;

    this.canvas.freeDrawingBrush = new PencilBrush(this.canvas);
    this.applyBrush();
    this.bindEvents();
    this.observeResize();

    if (this.readOnly) {
      this.canvas.selection = false;
      this.canvas.skipTargetFind = true;
      this.canvas.forEachObject((o) => (o.selectable = false));
    }
  }

  /* ------------------------------------------------------------------ setup */

  private bindEvents() {
    const c = this.canvas;
    c.on('mouse:down', this.onMouseDown);
    c.on('mouse:move', this.onMouseMove);
    c.on('mouse:up', this.onMouseUp);
    c.on('mouse:wheel', this.onWheel);
    c.on('path:created', this.onPathCreated);
    c.on('object:added', this.snapshot);
    c.on('object:modified', this.onModified);
    c.on('object:removed', this.snapshot);
    c.on('text:changed', this.onDirtyEvent);
    c.on('selection:created', this.onSelectionEvent);
    c.on('selection:updated', this.onSelectionEvent);
    c.on('selection:cleared', this.onSelectionCleared);
    this.attachTouch();

    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
  }

  private observeResize() {
    if (typeof ResizeObserver === 'undefined') return;
    this.resizeObserver = new ResizeObserver(() => {
      if (this.disposed) return;
      this.resize(this.host.clientWidth, this.host.clientHeight);
    });
    this.resizeObserver.observe(this.host);
  }

  private attachTouch() {
    const el = this.canvas.upperCanvasEl as unknown as HTMLElement;
    const start = (e: Event) => {
      const t = e as TouchEvent;
      if (t.touches.length !== 2) return;
      this.pinch = {
        dist: this.touchDistance(t),
        zoom: this.canvas.getZoom(),
        mid: this.touchMid(t),
      };
    };
    const move = (e: Event) => {
      const t = e as TouchEvent;
      if (!this.pinch || t.touches.length !== 2) return;
      t.preventDefault();
      const ratio = this.touchDistance(t) / (this.pinch.dist || 1);
      const zoom = clamp(this.pinch.zoom * ratio, MIN_ZOOM, MAX_ZOOM);
      this.canvas.zoomToPoint(this.pinch.mid, zoom);
      this.cb.onZoom(zoom);
    };
    const end = (e: Event) => {
      if ((e as TouchEvent).touches.length < 2) this.pinch = null;
    };
    for (const [name, fn] of [
      ['touchstart', start],
      ['touchmove', move],
      ['touchend', end],
      ['touchcancel', end],
    ] as Array<[string, EventListener]>) {
      el.addEventListener(name, fn, { passive: false });
      this.touchHandlers.push([name, fn]);
    }
  }

  private touchDistance(t: TouchEvent) {
    const [a, b] = [t.touches[0], t.touches[1]];
    return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
  }

  private touchMid(t: TouchEvent): Point {
    const rect = (this.canvas.upperCanvasEl as HTMLElement).getBoundingClientRect();
    const [a, b] = [t.touches[0], t.touches[1]];
    return new Point((a.clientX + b.clientX) / 2 - rect.left, (a.clientY + b.clientY) / 2 - rect.top);
  }

  /* ------------------------------------------------------------- public API */

  setTool(tool: Tool) {
    this.tool = tool;
    const c = this.canvas;
    c.isDrawingMode = !this.readOnly && tool === 'pen';
    c.selection = tool === 'select' && !this.readOnly;
    c.skipTargetFind = this.readOnly || ['hand', ...SHAPE_TOOLS, 'text', 'sticky'].includes(tool);
    c.defaultCursor = tool === 'hand' ? 'grab' : tool === 'select' ? 'default' : 'crosshair';
    if (tool !== 'select') c.discardActiveObject();
    if (tool === 'pen') this.applyBrush();
    c.requestRenderAll();
    this.cb.onToolChange(tool);
  }

  getTool() {
    return this.tool;
  }

  setStyle(patch: Partial<StyleState>) {
    this.style = { ...this.style, ...patch };
    this.applyBrush();
    // Live-apply to the current selection so the panel feels immediate.
    const active = this.canvas.getActiveObjects();
    if (active.length) {
      for (const obj of active) {
        if (patch.stroke !== undefined) {
          const isText = obj instanceof IText || obj instanceof Textbox;
          obj.set(isText ? { fill: patch.stroke } : { stroke: patch.stroke });
        }
        if (patch.fill !== undefined && !(obj instanceof IText || obj instanceof Textbox)) {
          obj.set({ fill: this.style.filled ? patch.fill : 'transparent' });
        }
        if (patch.filled !== undefined && !(obj instanceof IText || obj instanceof Textbox)) {
          obj.set({ fill: this.style.filled ? this.style.fill : 'transparent' });
        }
        if (patch.strokeWidth !== undefined) obj.set({ strokeWidth: patch.strokeWidth });
        if (patch.opacity !== undefined) obj.set({ opacity: patch.opacity });
        if (patch.fontSize !== undefined && (obj instanceof IText || obj instanceof Textbox)) {
          obj.set({ fontSize: patch.fontSize });
        }
        obj.setCoords();
      }
      this.canvas.requestRenderAll();
      this.emitSelection();
      this.snapshot();
    }
  }

  getStyle() {
    return { ...this.style };
  }

  /* ------------------------------------------------------------- scene I/O */

  /**
   * Load a scene document into the canvas.
   *
   * Never leaves a silently-empty board: the payload is normalized first, the
   * resulting object count is compared with the document's, and a per-object
   * salvage pass runs when fabric refuses the batch (`loadFromJSON` rejects or
   * drops objects it cannot enliven). The `LoadReport` goes to the caller, is
   * mirrored on `window.__wbLastLoad` for E2E checks, and `loadError` is set
   * when the scene could not be restored.
   */
  async load(doc: SceneDoc | null | undefined): Promise<LoadReport> {
    this.loading = true;
    const normalized = normalizeDoc(doc);
    let report: LoadReport = {
      expected: normalized.expected,
      loaded: 0,
      dropped: normalized.dropped,
      repaired: normalized.repaired,
      source: normalized.source,
      salvaged: false,
      error: null,
    };
    try {
      try {
        await this.canvas.loadFromJSON({ ...normalized.doc, background: 'transparent' });
      } catch (err) {
        // One un-enlivenable object used to abort the whole batch.
        report.error = err instanceof Error ? err.message : String(err);
      }
      let loaded = this.canvas.getObjects().length;
      if (loaded < normalized.kept) {
        const salvage = await this.loadObjectByObject(normalized.doc.objects);
        report = { ...report, dropped: [...report.dropped, ...salvage.dropped], salvaged: true };
        loaded = this.canvas.getObjects().length;
      }
      report.loaded = loaded;
      if (loaded !== normalized.kept && !report.error) {
        report.error = `اتحمّل ${loaded} من ${normalized.kept} عنصر`;
      }
      this.canvas.backgroundColor = 'transparent';
      this.canvas.requestRenderAll();
      if (this.readOnly) {
        this.canvas.selection = false;
        this.canvas.skipTargetFind = true;
        this.canvas.forEachObject((o) => {
          o.selectable = false;
          o.evented = false;
        });
      }
      this.history = [];
      this.historyIndex = -1;
      this.pushHistory();
    } finally {
      this.loading = false;
      this.lastLoad = report;
      (window as unknown as { __wbLastLoad?: LoadReport }).__wbLastLoad = report;
    }
    return report;
  }

  /** Last load diagnostics (also available as `window.__wbLastLoad`). */
  lastLoad: LoadReport | null = null;

  /** True when the canvas holds exactly what the source document claimed. */
  assertLoaded(expected: number = this.lastLoad?.expected ?? 0): boolean {
    return this.canvas.getObjects().length === expected;
  }

  /**
   * Fallback loader: enliven objects one by one so a single broken object can
   * cost one shape instead of the entire board.
   */
  private async loadObjectByObject(objects: Record<string, unknown>[]) {
    const dropped: LoadReport['dropped'] = [];
    this.canvas.clear();
    for (let i = 0; i < objects.length; i += 1) {
      const raw = objects[i];
      try {
        const [enlivened] = (await util.enlivenObjects([raw])) as FabricObject[];
        if (!enlivened) {
          dropped.push({ path: `objects[${i}]`, type: String(raw.type ?? '-'), reason: 'not enlivened' });
          continue;
        }
        this.canvas.add(enlivened);
      } catch (err) {
        dropped.push({
          path: `objects[${i}]`,
          type: String(raw.type ?? '-'),
          reason: err instanceof Error ? err.message : String(err),
        });
      }
    }
    this.canvas.requestRenderAll();
    return { dropped };
  }

  toDoc(): SceneDoc {
    const json = this.canvas.toJSON() as unknown as SceneDoc;
    return { ...json, background: 'transparent' };
  }

  /** Small PNG for the board cards; null when the scene is empty. */
  thumbnail(maxChars = 90_000): string | null {
    if (!this.canvas.getObjects().length) return null;
    const url = this.canvas.toDataURL({ format: 'png', multiplier: 0.22, quality: 0.6 });
    return url.length <= maxChars ? url : null;
  }

  exportPNG(multiplier = 2): string {
    return this.canvas.toDataURL({ format: 'png', multiplier });
  }

  async copyAsImage(): Promise<void> {
    const url = this.canvas.toDataURL({ format: 'png', multiplier: 2 });
    const blob = await (await fetch(url)).blob();
    const anyWin = window as unknown as { ClipboardItem?: typeof ClipboardItem };
    if (!navigator.clipboard || !anyWin.ClipboardItem) throw new Error('المتصفح مش بيدعم نسخ الصور');
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
  }

  /* ----------------------------------------------------------- object ops */

  deleteSelection() {
    const active = this.canvas.getActiveObjects();
    if (!active.length) return;
    this.canvas.discardActiveObject();
    for (const obj of active) this.canvas.remove(obj);
    this.canvas.requestRenderAll();
    this.snapshot();
    this.cb.onDirty();
    this.emitSelection();
  }

  async copySelection() {
    const active = this.canvas.getActiveObjects();
    if (!active.length) return;
    this.clipboard = await Promise.all(active.map((o) => o.clone()));
  }

  async paste() {
    if (!this.clipboard.length) return;
    const clones = await Promise.all(this.clipboard.map((o) => o.clone()));
    this.canvas.discardActiveObject();
    for (const o of clones) {
      o.set({ left: (o.left ?? 0) + 24, top: (o.top ?? 0) + 24, evented: true });
      this.canvas.add(o);
    }
    this.selectAll(clones);
    this.cb.onDirty();
  }

  async duplicate() {
    const active = this.canvas.getActiveObjects();
    if (!active.length) return;
    const clones = await Promise.all(active.map((o) => o.clone()));
    this.canvas.discardActiveObject();
    for (const o of clones) {
      o.set({ left: (o.left ?? 0) + 24, top: (o.top ?? 0) + 24 });
      this.canvas.add(o);
    }
    this.selectAll(clones);
    this.cb.onDirty();
  }

  private selectAll(objs: FabricObject[]) {
    if (!objs.length) return;
    if (objs.length === 1) {
      this.canvas.setActiveObject(objs[0]);
    } else {
      // ActiveSelection — never `new Group()`, which would reparent the objects.
      this.canvas.setActiveObject(new ActiveSelection(objs, { canvas: this.canvas }));
    }
    this.canvas.requestRenderAll();
    this.emitSelection();
  }

  async addImageFile(file: File): Promise<void> {
    const dataUrl = await readAsDataURL(file);
    const img = await FabricImage.fromURL(dataUrl);
    const maxW = Math.min(480, this.canvas.getWidth() * 0.6);
    const maxH = Math.min(480, this.canvas.getHeight() * 0.6);
    const scale = Math.min(maxW / (img.width || maxW), maxH / (img.height || maxH), 1);
    const center = this.viewportCenter();
    img.set({
      left: center.x - ((img.width || 0) * scale) / 2,
      top: center.y - ((img.height || 0) * scale) / 2,
      scaleX: scale,
      scaleY: scale,
    });
    this.canvas.add(img);
    this.canvas.setActiveObject(img);
    this.canvas.requestRenderAll();
    this.snapshot();
    this.cb.onDirty();
    this.cb.onToolDone();
  }

  clear() {
    const objs = this.canvas.getObjects();
    if (!objs.length) return;
    this.canvas.discardActiveObject();
    this.canvas.remove(...objs);
    this.canvas.requestRenderAll();
    this.snapshot();
    this.cb.onDirty();
    this.emitSelection();
  }

  /* ------------------------------------------------------------- history */

  private pushHistory() {
    const json = JSON.stringify(this.canvas.toJSON());
    this.history = this.history.slice(0, this.historyIndex + 1);
    this.history.push(json);
    if (this.history.length > HISTORY_LIMIT) this.history.shift();
    this.historyIndex = this.history.length - 1;
  }

  private snapshot = () => {
    if (this.loading || this.drawing || this.erasing || this.readOnly) return;
    this.pushHistory();
  };

  private onModified = () => {
    this.snapshot();
    this.cb.onDirty();
    this.emitSelection();
  };

  private onDirtyEvent = () => {
    if (this.loading) return;
    this.cb.onDirty();
  };

  canUndo() {
    return this.historyIndex > 0;
  }

  canRedo() {
    return this.historyIndex < this.history.length - 1;
  }

  undo() {
    if (!this.canUndo()) return;
    this.historyIndex -= 1;
    void this.applyHistory(this.history[this.historyIndex], false);
  }

  redo() {
    if (!this.canRedo()) return;
    this.historyIndex += 1;
    void this.applyHistory(this.history[this.historyIndex], false);
  }

  private async applyHistory(json: string, record: boolean) {
    this.loading = true;
    try {
      await this.canvas.loadFromJSON(JSON.parse(json));
      this.canvas.backgroundColor = 'transparent';
      this.canvas.requestRenderAll();
      this.emitSelection();
    } finally {
      this.loading = false;
    }
    if (record) this.pushHistory();
    this.cb.onDirty();
  }

  /* ---------------------------------------------------------------- view */

  zoomBy(factor: number) {
    const center = new Point(this.canvas.getWidth() / 2, this.canvas.getHeight() / 2);
    const zoom = clamp(this.canvas.getZoom() * factor, MIN_ZOOM, MAX_ZOOM);
    this.canvas.zoomToPoint(center, zoom);
    this.cb.onZoom(zoom);
  }

  zoomTo(zoom: number) {
    const center = new Point(this.canvas.getWidth() / 2, this.canvas.getHeight() / 2);
    const z = clamp(zoom, MIN_ZOOM, MAX_ZOOM);
    this.canvas.zoomToPoint(center, z);
    this.cb.onZoom(z);
  }

  resetView() {
    this.canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
    this.cb.onZoom(1);
  }

  fitToContent(maxZoom: number = MAX_ZOOM) {
    const objs = this.canvas.getObjects().filter((o) => o.visible !== false);
    if (!objs.length) {
      this.resetView();
      return;
    }
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const o of objs) {
      const r = o.getBoundingRect();
      minX = Math.min(minX, r.left);
      minY = Math.min(minY, r.top);
      maxX = Math.max(maxX, r.left + r.width);
      maxY = Math.max(maxY, r.top + r.height);
    }
    const pad = 60;
    const w = maxX - minX + pad * 2;
    const h = maxY - minY + pad * 2;
    const zoom = clamp(
      Math.min(this.canvas.getWidth() / w, this.canvas.getHeight() / h),
      MIN_ZOOM,
      Math.min(MAX_ZOOM, maxZoom),
    );
    this.canvas.setViewportTransform([
      zoom,
      0,
      0,
      zoom,
      this.canvas.getWidth() / 2 - ((minX + maxX) / 2) * zoom,
      this.canvas.getHeight() / 2 - ((minY + maxY) / 2) * zoom,
    ]);
    this.cb.onZoom(zoom);
  }

  resize(width: number, height: number) {
    const w = Math.max(120, Math.floor(width));
    const h = Math.max(120, Math.floor(height));
    if (w === this.canvas.getWidth() && h === this.canvas.getHeight()) return;
    this.canvas.setDimensions({ width: w, height: h });
    this.canvas.requestRenderAll();
  }

  private viewportCenter(): Point {
    const vpt = this.canvas.viewportTransform;
    const zoom = this.canvas.getZoom();
    return new Point(
      (this.canvas.getWidth() / 2 - vpt[4]) / zoom,
      (this.canvas.getHeight() / 2 - vpt[5]) / zoom,
    );
  }

  /* ------------------------------------------------------------ pointer */

  private onMouseDown = (opt: TPointerEventInfo) => {
    if (this.readOnly) return;
    const e = opt.e as TPointerEvent & MouseEvent;
    if (e.button === 1 || this.tool === 'hand' || this.spaceDown) {
      this.panFrom = {
        x: e.clientX,
        y: e.clientY,
        tx: this.canvas.viewportTransform[4],
        ty: this.canvas.viewportTransform[5],
      };
      this.canvas.setCursor('grabbing');
      return;
    }

    if (this.tool === 'eraser') {
      this.erasing = true;
      this.eraseAt(opt.target ?? null);
      return;
    }

    if (this.tool === 'select') return;

    const p = this.canvas.getScenePoint(e);

    if (this.tool === 'text') {
      this.addText(p);
      return;
    }
    if (this.tool === 'sticky') {
      this.addSticky(p);
      return;
    }
    if (SHAPE_TOOLS.includes(this.tool)) {
      this.drawing = true;
      this.start = p;
      this.createDraft(p, p);
    }
  };

  private onMouseMove = (opt: TPointerEventInfo) => {
    const e = opt.e as TPointerEvent & MouseEvent;

    if (this.panFrom) {
      const vpt = this.canvas.viewportTransform.slice() as [number, number, number, number, number, number];
      vpt[4] = this.panFrom.tx + (e.clientX - this.panFrom.x);
      vpt[5] = this.panFrom.ty + (e.clientY - this.panFrom.y);
      this.canvas.setViewportTransform(vpt);
      this.canvas.requestRenderAll();
      return;
    }

    if (this.erasing) {
      this.eraseAt(opt.target ?? null);
      return;
    }

    if (this.drawing && this.start) {
      const p = this.canvas.getScenePoint(e);
      this.updateDraft(this.start, p);
    }
  };

  private onMouseUp = () => {
    if (this.panFrom) {
      this.panFrom = null;
      this.canvas.setCursor(this.tool === 'hand' ? 'grab' : 'default');
    }
    if (this.erasing) {
      this.erasing = false;
      this.snapshot();
      this.cb.onDirty();
    }
    if (this.drawing) {
      this.finishDraft();
    }
  };

  private eraseAt(target: FabricObject | null) {
    if (!target) return;
    this.canvas.remove(target);
    this.canvas.requestRenderAll();
    this.emitSelection();
  }

  private onWheel = (opt: TPointerEventInfo<WheelEvent>) => {
    const e = opt.e;
    e.preventDefault();
    e.stopPropagation();
    const delta = e.deltaY;
    const zoom = clamp(this.canvas.getZoom() * 0.999 ** delta, MIN_ZOOM, MAX_ZOOM);
    this.canvas.zoomToPoint(new Point(e.offsetX, e.offsetY), zoom);
    this.cb.onZoom(zoom);
  };

  private onPathCreated = () => {
    this.cb.onDirty();
  };

  /* ------------------------------------------------------------- drafts */

  private createDraft(a: Point, b: Point) {
    const obj = this.makeShape(this.tool, a, b);
    if (!obj) return;
    this.draft = obj;
    this.canvas.add(obj);
    if (this.tool !== 'arrow') this.canvas.setActiveObject(obj);
  }

  private updateDraft(a: Point, b: Point) {
    if (!this.draft) return;
    const next = this.makeShape(this.tool, a, b);
    if (!next) return;
    const index = this.canvas.getObjects().indexOf(this.draft);
    this.canvas.remove(this.draft);
    this.draft = next;
    // keep z-order stable while the user drags
    if (index >= 0) this.canvas.insertAt(index, next);
    else this.canvas.add(next);
    this.canvas.requestRenderAll();
  }

  private finishDraft() {
    this.drawing = false;
    const obj = this.draft;
    this.draft = null;
    if (!obj) return;
    const w = (obj.width ?? 0) * (obj.scaleX ?? 1);
    const h = (obj.height ?? 0) * (obj.scaleY ?? 1);
    if (Math.max(w, h) < SHAPE_MIN) {
      // a click, not a drag → drop a default-sized shape so the tool feels alive
      const size = 120;
      obj.set({
        left: (obj.left ?? 0) - size / 2,
        top: (obj.top ?? 0) - size / 2,
        width: this.tool === 'arrow' ? 160 : size,
        height: this.tool === 'arrow' ? 0.001 : size,
      });
      obj.setCoords();
    }
    this.canvas.setActiveObject(obj);
    this.canvas.requestRenderAll();
    this.snapshot();
    this.cb.onDirty();
    this.emitSelection();
    this.setTool('select');
    this.cb.onToolDone();
  }

  private makeShape(tool: Tool, a: Point, b: Point): FabricObject | null {
    const { stroke, fill, filled, strokeWidth, opacity } = this.style;
    const left = Math.min(a.x, b.x);
    const top = Math.min(a.y, b.y);
    const width = Math.max(Math.abs(b.x - a.x), 1);
    const height = Math.max(Math.abs(b.y - a.y), 1);
    const common = {
      stroke,
      strokeWidth,
      opacity,
      fill: filled ? fill : 'transparent',
      strokeUniform: true,
      objectCaching: false,
      left,
      top,
      width,
      height,
    };

    if (tool === 'rect') return new Rect({ ...common, rx: 6, ry: 6 });
    if (tool === 'circle') {
      const radius = Math.max(width, height) / 2;
      return new Circle({ ...common, radius, width: radius * 2, height: radius * 2 });
    }
    if (tool === 'triangle') return new Triangle({ ...common });
    if (tool === 'arrow') return this.makeArrow(a, b);
    return null;
  }

  private makeArrow(a: Point, b: Point): FabricObject {
    const { stroke, strokeWidth, opacity } = this.style;
    const angle = Math.atan2(b.y - a.y, b.x - a.x);
    const headLen = 16 + strokeWidth * 2;
    const shaft = new Line([a.x, a.y, b.x, b.y], {
      stroke,
      strokeWidth,
      opacity,
      strokeLineCap: 'round',
    });
    const head = new Triangle({
      left: b.x,
      top: b.y,
      width: headLen,
      height: headLen,
      fill: stroke,
      originX: 'center',
      originY: 'center',
      angle: (angle * 180) / Math.PI + 90,
      opacity,
    });
    return new Group([shaft, head], { opacity, objectCaching: false });
  }

  private addText(p: Point) {
    const { stroke, fontSize, opacity } = this.style;
    const text = new IText('', {
      left: p.x,
      top: p.y,
      fill: stroke,
      fontSize,
      opacity,
      fontFamily: "'Cairo', 'Noto Kufi Arabic', 'Segoe UI', Tahoma, sans-serif",
      direction: 'rtl',
      textAlign: 'right',
      editingBorderColor: '#6366f1',
      cursorColor: '#818cf8',
      padding: 4,
    });
    this.canvas.add(text);
    this.canvas.setActiveObject(text);
    text.enterEditing();
    text.selectAll();
    this.canvas.requestRenderAll();
    this.cb.onDirty();
    this.setTool('select');
    this.cb.onToolDone();
  }

  private addSticky(p: Point) {
    const { fontSize, opacity } = this.style;
    const size = 190;
    const sticky = new Textbox(STICKY_DEFAULT, {
      left: p.x - size / 2,
      top: p.y - size / 2,
      width: size,
      fontSize,
      fill: '#3f2d0b',
      backgroundColor: '#fde68a',
      opacity,
      padding: 14,
      fontFamily: "'Cairo', 'Noto Kufi Arabic', 'Segoe UI', Tahoma, sans-serif",
      direction: 'rtl',
      textAlign: 'right',
      splitByGrapheme: true,
      shadow: new Shadow({ color: 'rgba(0,0,0,0.35)', blur: 24, offsetY: 10 }),
      editingBorderColor: '#b45309',
      cursorColor: '#3f2d0b',
      stroke: 'rgba(180,83,9,0.45)',
      strokeWidth: 1,
      strokeUniform: true,
    });
    this.canvas.add(sticky);
    this.canvas.setActiveObject(sticky);
    this.canvas.requestRenderAll();
    this.snapshot();
    this.cb.onDirty();
    this.setTool('select');
    this.cb.onToolDone();
  }

  /* ---------------------------------------------------------- selection */

  private onSelectionEvent = () => this.emitSelection();
  private onSelectionCleared = () => this.emitSelection();

  private emitSelection() {
    const active = this.canvas.getActiveObjects();
    if (!active.length) {
      this.cb.onSelection(EMPTY_SELECTION);
      return;
    }
    const first = active[0];
    const isText = first instanceof IText || first instanceof Textbox;
    this.cb.onSelection({
      count: active.length,
      fill: isText ? null : ((first.fill as string) ?? null),
      stroke: isText ? ((first.fill as string) ?? null) : ((first.stroke as string) ?? null),
      strokeWidth: first.strokeWidth ?? null,
      opacity: first.opacity ?? 1,
    });
  }

  /* ------------------------------------------------------------ keyboard */

  private onKeyDown = (e: KeyboardEvent) => {
    if (this.readOnly) return;
    const target = e.target as HTMLElement | null;
    const typing =
      !!target &&
      (target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable ||
        (this.canvas.getActiveObject() as IText | null)?.isEditing);

    if (e.code === 'Space' && !typing) {
      this.spaceDown = true;
      this.canvas.defaultCursor = 'grab';
    }

    if (typing) return;

    const meta = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();

    if (meta && key === 'z') {
      e.preventDefault();
      if (e.shiftKey) this.redo();
      else this.undo();
      return;
    }
    if (meta && key === 'y') {
      e.preventDefault();
      this.redo();
      return;
    }
    if (meta && key === 'd') {
      e.preventDefault();
      void this.duplicate();
      return;
    }
    if (meta && key === 'c') {
      void this.copySelection();
      return;
    }
    if (meta && key === 'v') {
      void this.paste();
      return;
    }
    if (meta && key === 'a') {
      e.preventDefault();
      const all = this.canvas.getObjects();
      if (all.length) this.selectAll(all);
      return;
    }
    if (key === 'delete' || key === 'backspace') {
      e.preventDefault();
      this.deleteSelection();
      return;
    }
    if (key === 'escape') {
      this.canvas.discardActiveObject();
      this.canvas.requestRenderAll();
      this.setTool('select');
      return;
    }

    const SHORTCUTS: Record<string, Tool> = {
      v: 'select',
      p: 'pen',
      e: 'eraser',
      r: 'rect',
      o: 'circle',
      t: 'text',
      n: 'sticky',
      a: 'arrow',
      g: 'triangle',
      h: 'hand',
    };
    if (!meta && !e.altKey && SHORTCUTS[key]) {
      e.preventDefault();
      this.setTool(SHORTCUTS[key]);
    }
  };

  private onKeyUp = (e: KeyboardEvent) => {
    if (e.code === 'Space') {
      this.spaceDown = false;
      this.canvas.defaultCursor = this.tool === 'hand' ? 'grab' : 'default';
    }
  };

  private applyBrush() {
    const brush = this.canvas.freeDrawingBrush;
    if (!brush) return;
    brush.color = this.style.stroke;
    brush.width = this.style.strokeWidth * 1.6;
  }

  /* --------------------------------------------------------------- teardown */

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    this.resizeObserver?.disconnect();
    const el = this.canvas.upperCanvasEl as unknown as HTMLElement;
    for (const [name, fn] of this.touchHandlers) el.removeEventListener(name, fn);
    this.touchHandlers = [];
    void this.canvas.dispose();
    this.host.innerHTML = '';
  }
}

export function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v));
}

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('مش قادر أقرأ الملف'));
    reader.readAsDataURL(file);
  });
}
