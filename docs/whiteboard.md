# Whiteboard — canvas

A single-page canvas where a user draws with mouse or touch, adds shapes, and moves,
resizes and rotates them. Boards are stored as fabric.js JSON and autosaved.

## Tools

| Tool | Behaviour |
|---|---|
| Pen | freehand stroke, variable width and colour |
| Eraser | removes objects under the pointer |
| Rectangle / Circle / Triangle | drag to draw, optional fill |
| Arrow / Line | drag to draw |
| Text | click to place an editable text box |
| Sticky note | coloured note with text |
| Image | upload and place |
| Select | move, resize from handles, rotate, duplicate, delete |
| Hand | pan the canvas |
| Zoom | wheel, pinch on touch, fit-to-content, reset 100% |

## Extras

- Undo / redo (Ctrl+Z, Ctrl+Shift+Z) and keyboard shortcuts (V, P, E, R, O, G, A, T, N, H)
- Colour palette, stroke width, opacity, fill toggle, font sizes
- Optional dot grid background
- Export PNG / copy as image
- Read-only share link per board
- Autosave ~2 s after the last change, with a visible "saving / saved" indicator

## Acceptance criteria (16, Given/When/Then)

Covering: draw, erase, each shape, text, sticky note, move, resize, rotate, delete,
undo/redo, zoom/pan, autosave + reload persistence, PNG export, touch on a 390 px viewport,
and a read-only share link. Each criterion names a measurable proof (element count, angle,
`updated_at`, HTTP status) rather than "looks right".

## Known risk

The transform stack (move + scale + rotate on one object) drifts if `left/top` are not
normalised together with `scaleX/scaleY`; persistence must store the resolved transform.
