/** Shared types mirroring the FastAPI contract (backend/app/schemas.py). */

export type SceneDoc = {
  version?: string;
  objects: Record<string, unknown>[];
  background?: string;
};

export type BoardSummary = {
  id: string;
  name: string;
  color: string;
  version: number;
  object_count: number;
  has_thumb: boolean;
  share_token: string | null;
  created_at: string;
  updated_at: string;
};

export type Board = {
  id: string;
  name: string;
  color: string;
  doc: SceneDoc;
  thumb: string | null;
  share_token: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

export type ShareInfo = { share_token: string; share_url: string };

export type Tool =
  | 'select'
  | 'pen'
  | 'eraser'
  | 'rect'
  | 'circle'
  | 'triangle'
  | 'arrow'
  | 'text'
  | 'sticky'
  | 'image'
  | 'hand';

export type StyleState = {
  stroke: string;
  fill: string;
  filled: boolean;
  strokeWidth: number;
  opacity: number;
  fontSize: number;
};

export type SaveState = 'idle' | 'dirty' | 'saving' | 'saved' | 'error' | 'conflict';

export const PALETTE = [
  '#f8fafc',
  '#94a3b8',
  '#6366f1',
  '#8b5cf6',
  '#ec4899',
  '#f43f5e',
  '#f97316',
  '#eab308',
  '#22c55e',
  '#14b8a6',
  '#06b6d4',
  '#3b82f6',
  '#0ea5e9',
  '#1e293b',
] as const;

export const STICKY_COLORS = [
  '#fde68a',
  '#fecaca',
  '#bbf7d0',
  '#bfdbfe',
  '#e9d5ff',
  '#fed7aa',
] as const;
