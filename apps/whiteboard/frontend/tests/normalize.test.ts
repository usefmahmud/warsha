/**
 * Unit tests for the doc normalizer — `node --test tests/` (Node ≥ 22.18 strips
 * TypeScript on the fly, no extra dev dependency needed).
 *
 * The invariant that matters for WB-3/AC-13: for any document the API hands us,
 * `kept` is the number fabric must end up with, and nothing is ever silently
 * discarded — every loss shows up in `dropped`.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { normalizeDoc } from '../src/editor/normalize.ts';

const healthy = {
  version: '6.9.1',
  objects: [
    { type: 'circle', left: 380, top: 90, width: 140, height: 140, radius: 70, scaleX: 1, scaleY: 1 },
    { type: 'rect', left: 547, top: 268, width: 167, height: 123, scaleX: 1, scaleY: 1 },
    { type: 'triangle', left: 560, top: 90, width: 140, height: 140 },
    {
      type: 'path',
      left: 238,
      top: 25,
      path: [
        ['M', 0, 0],
        ['L', 100, 40],
      ],
    },
    { type: 'i-text', left: 120, top: 520, text: 'مرحبا', fontSize: 24 },
    { type: 'textbox', left: 465, top: 425, width: 190, text: 'اكتب هنا…' },
    {
      type: 'group',
      left: 346,
      top: 95,
      objects: [
        { type: 'line', x1: 0, y1: 0, x2: 100, y2: 20 },
        { type: 'triangle', left: 10, top: 10, width: 16, height: 16 },
      ],
    },
  ],
  background: 'transparent',
};

test('a healthy doc keeps every object and reports nothing dropped', () => {
  const r = normalizeDoc(healthy);
  assert.equal(r.expected, 7);
  assert.equal(r.kept, 7);
  assert.equal(r.doc.objects.length, 7);
  assert.deepEqual(r.dropped, []);
  assert.equal(r.source, 'ok');
  assert.equal(r.doc.background, 'transparent');
});

test('a doubled-encoded doc (JSON string) is decoded, not silently dropped', () => {
  const r = normalizeDoc(JSON.stringify(healthy));
  assert.equal(r.source, 'json-string');
  assert.equal(r.expected, 7);
  assert.equal(r.kept, 7);
});

test('unparsable payload yields an empty doc and no fake objects', () => {
  const r = normalizeDoc('{not json');
  assert.equal(r.source, 'invalid');
  assert.equal(r.expected, 0);
  assert.equal(r.kept, 0);
  assert.equal(r.doc.objects.length, 0);
});

test('null / undefined doc is an empty scene', () => {
  for (const value of [null, undefined, {}]) {
    const r = normalizeDoc(value);
    assert.equal(r.kept, 0);
    assert.equal(r.expected, 0);
  }
});

test('an unknown object type is reported instead of poisoning the batch', () => {
  const r = normalizeDoc({
    objects: [{ type: 'mysteryShape', left: 10, top: 10 }, ...healthy.objects],
  });
  assert.equal(r.expected, 8);
  assert.equal(r.kept, 7);
  assert.equal(r.dropped.length, 1);
  assert.match(r.dropped[0].reason, /unknown object type/);
});

test('objects that is not an array is reported', () => {
  const r = normalizeDoc({ objects: { 0: { type: 'rect' } } });
  assert.equal(r.kept, 0);
  assert.equal(r.dropped.length, 1);
  assert.match(r.dropped[0].reason, /not an array/);
});

test('non-numeric geometry is repaired to finite numbers', () => {
  const r = normalizeDoc({
    objects: [{ type: 'rect', left: '380', top: NaN, width: '140', scaleX: null }],
  });
  assert.equal(r.kept, 1);
  const obj = r.doc.objects[0];
  assert.equal(obj.left, 380);
  assert.equal(obj.top, 0);
  assert.equal(obj.width, 140);
  assert.equal(obj.scaleX, 1);
  assert.ok(Number.isFinite(obj.left as number));
  assert.ok(r.repaired >= 3);
});

test('a path with broken command data is dropped, others survive', () => {
  const r = normalizeDoc({
    objects: [{ type: 'path', path: 'nope' }, { type: 'rect', left: 0, top: 0 }],
  });
  assert.equal(r.kept, 1);
  assert.equal(r.dropped.length, 1);
  assert.match(r.dropped[0].reason, /broken path/);
});

test('an image without a src is dropped', () => {
  const r = normalizeDoc({ objects: [{ type: 'image', left: 0, top: 0 }] });
  assert.equal(r.kept, 0);
  assert.match(r.dropped[0].reason, /image without src/);
});

test('a group keeps its healthy children and reports the broken one', () => {
  const r = normalizeDoc({
    objects: [
      {
        type: 'group',
        left: 0,
        top: 0,
        objects: [
          { type: 'rect', left: 0, top: 0 },
          { type: 'mysteryShape' },
        ],
      },
    ],
  });
  assert.equal(r.kept, 1);
  const group = r.doc.objects[0] as { objects: unknown[] };
  assert.equal(group.objects.length, 1);
  assert.equal(r.dropped.length, 1);
  assert.match(r.dropped[0].path, /objects\[0\]\.objects\[1\]/);
});

test('a group whose children are all broken is dropped, not kept empty', () => {
  const r = normalizeDoc({ objects: [{ type: 'group', objects: [{ type: 'mysteryShape' }] }] });
  assert.equal(r.kept, 0);
  assert.equal(r.dropped.length, 2);
});

test('the stored 15-object board keeps all 15 objects', () => {
  // Regression guard for the reported bug: the deployed board reported
  // `object_count: 15` while the canvas showed 0 — the count must survive.
  const objects = Array.from({ length: 15 }, (_, i) => ({
    type: i % 3 === 0 ? 'rect' : i % 3 === 1 ? 'circle' : 'path',
    left: i * 10,
    top: i * 5,
    width: 40,
    height: 40,
    ...(i % 3 === 2 ? { path: [['M', 0, 0], ['L', 5, 5]] } : {}),
  }));
  const r = normalizeDoc({ version: '6.9.1', objects });
  assert.equal(r.expected, 15);
  assert.equal(r.kept, 15);
  assert.deepEqual(r.dropped, []);
});
