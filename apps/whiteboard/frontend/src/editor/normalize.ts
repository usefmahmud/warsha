/**
 * Scene-document hygiene — the guard between the API and fabric.
 *
 * A board `doc` is stored as free-form JSON, so it can arrive doubled-encoded
 * (`"{\"objects\":…}"`), truncated, or holding object types/path data this
 * bundle cannot enliven. When that happens `canvas.loadFromJSON()` either
 * rejects or silently no-ops, and the board renders empty with no visible
 * error. Everything repairable is repaired here; anything unrecoverable is
 * reported (`dropped`) so the UI can say so instead of showing a blank board.
 *
 * Pure module: no fabric / DOM imports, so it is unit-testable with `node --test`.
 */

import type { SceneDoc } from '../types';

export type DroppedObject = { path: string; type: string; reason: string };

export type NormalizedDoc = {
  doc: SceneDoc;
  /** Objects the source document claimed to hold (before repairs). */
  expected: number;
  /** Objects kept after repairs — this is what fabric must end up with. */
  kept: number;
  dropped: DroppedObject[];
  /** Objects whose scalar fields had to be coerced into valid numbers. */
  repaired: number;
  source: 'ok' | 'json-string' | 'invalid';
};

/** Object types this build's fabric registry can enliven. */
const KNOWN_TYPES = new Set([
  'rect',
  'circle',
  'ellipse',
  'triangle',
  'line',
  'polyline',
  'polygon',
  'path',
  'group',
  'image',
  'text',
  'i-text',
  'textbox',
]);

/** Tolerated spellings → the `type` string fabric v6 registers. */
const TYPE_ALIASES: Record<string, string> = {
  rect: 'rect',
  rectangle: 'rect',
  circle: 'circle',
  ellipse: 'ellipse',
  triangle: 'triangle',
  line: 'line',
  polyline: 'polyline',
  polygon: 'polygon',
  path: 'path',
  group: 'group',
  image: 'image',
  itext: 'i-text',
  'i-text': 'i-text',
  itextbox: 'i-text',
  text: 'text',
  textbox: 'textbox',
};

const NUMERIC_FIELDS = [
  'left',
  'top',
  'width',
  'height',
  'scaleX',
  'scaleY',
  'angle',
  'opacity',
  'strokeWidth',
  'strokeMiterLimit',
  'strokeDashOffset',
  'radius',
  'rx',
  'ry',
  'skewX',
  'skewY',
  'fontSize',
] as const;

function asFinite(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function parseJson(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return undefined;
  }
}

function resolveType(raw: Record<string, unknown>): string | null {
  const attempt = String(raw.type ?? '').trim().toLowerCase().replace(/[^a-z-]/g, '');
  const type = TYPE_ALIASES[attempt];
  return type && KNOWN_TYPES.has(type) ? type : null;
}

/** Repair one serialized fabric object; `null` means "drop it". */
function repairObject(
  raw: unknown,
  path: string,
  dropped: DroppedObject[],
  counter: { repaired: number },
  depth = 0,
): Record<string, unknown> | null {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    dropped.push({ path, type: '-', reason: 'not an object' });
    return null;
  }
  const obj = raw as Record<string, unknown>;
  const type = resolveType(obj);
  if (!type) {
    dropped.push({ path, type: String(obj.type ?? 'missing'), reason: 'unknown object type' });
    return null;
  }

  if (type === 'path') {
    const p = obj.path;
    if (!Array.isArray(p) || p.length === 0 || !p.every((cmd) => Array.isArray(cmd) && cmd.length > 0)) {
      dropped.push({ path, type, reason: 'broken path data' });
      return null;
    }
  }
  if (type === 'image') {
    if (typeof obj.src !== 'string' || obj.src.length === 0) {
      dropped.push({ path, type, reason: 'image without src' });
      return null;
    }
  }

  const next: Record<string, unknown> = { ...obj, type };
  for (const field of NUMERIC_FIELDS) {
    if (!(field in next)) continue;
    const value = next[field];
    if (value === null || value === undefined) {
      delete next[field];
      counter.repaired += 1;
      continue;
    }
    const num = asFinite(value);
    if (num === null) {
      delete next[field];
      counter.repaired += 1;
    } else if (num !== value) {
      next[field] = num;
      counter.repaired += 1;
    }
  }
  // A non-finite / missing transform would place the object at NaN coords.
  next.left = asFinite(next.left) ?? 0;
  next.top = asFinite(next.top) ?? 0;
  next.scaleX = asFinite(next.scaleX) ?? 1;
  next.scaleY = asFinite(next.scaleY) ?? 1;
  next.angle = asFinite(next.angle) ?? 0;
  next.opacity = asFinite(next.opacity) ?? 1;

  if (type === 'group' && obj.objects !== undefined) {
    if (depth > 6) {
      dropped.push({ path, type, reason: 'group nesting too deep' });
      return null;
    }
    const children = repairList(obj.objects, `${path}.objects`, dropped, counter, depth + 1);
    if (children.length === 0) {
      dropped.push({ path, type, reason: 'group with no usable children' });
      return null;
    }
    next.objects = children;
  }

  return next;
}

function repairList(
  raw: unknown,
  path: string,
  dropped: DroppedObject[],
  counter: { repaired: number },
  depth = 0,
): Record<string, unknown>[] {
  const list = parseJson(raw);
  if (!Array.isArray(list)) return [];
  const out: Record<string, unknown>[] = [];
  list.forEach((entry, i) => {
    const fixed = repairObject(entry, `${path}[${i}]`, dropped, counter, depth);
    if (fixed) out.push(fixed);
  });
  return out;
}

/** Coerce any API `doc` payload into something fabric can always load. */
export function normalizeDoc(input: unknown): NormalizedDoc {
  const dropped: DroppedObject[] = [];
  const counter = { repaired: 0 };
  let source: NormalizedDoc['source'] = 'ok';

  let parsed = input;
  if (typeof parsed === 'string') {
    const decoded = parseJson(parsed);
    source = decoded === undefined ? 'invalid' : 'json-string';
    parsed = decoded;
  }
  if (Array.isArray(parsed)) parsed = { objects: parsed };

  const rawList =
    parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>).objects
      : undefined;

  const declared = parseJson(rawList);
  if (rawList !== undefined && !Array.isArray(declared)) {
    dropped.push({ path: 'objects', type: '-', reason: 'objects is not an array' });
  }
  const expected = Array.isArray(declared) ? declared.length : 0;
  const objects = repairList(rawList, 'objects', dropped, counter);

  return {
    doc: { version: String((parsed as Record<string, unknown> | null)?.version ?? '6.9.1'), objects, background: 'transparent' },
    expected,
    kept: objects.length,
    dropped,
    repaired: counter.repaired,
    source,
  };
}
