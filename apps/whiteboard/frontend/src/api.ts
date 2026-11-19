/** Typed fetch wrapper for the Whiteboard API. Same-origin by default. */

import type { Board, BoardSummary, SceneDoc, ShareInfo } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }

  /** True for the autosave optimistic-concurrency rejection (409). */
  get isConflict() {
    return this.status === 409;
  }

  /** The server's current board when a conflict was detected. */
  get conflictBoard(): Board | null {
    const d = this.detail as { board?: Board } | null;
    return d && typeof d === 'object' && d.board ? d.board : null;
  }

  get messageAr(): string {
    if (this.status === 409) return 'البورد اتعدّل من مكان تاني';
    if (this.status === 404) return 'البورد مش موجود';
    if (this.status === 413) return 'المستند كبير جدًا';
    if (typeof this.detail === 'string') return this.detail;
    const d = this.detail as { message?: string; detail?: string } | null;
    return d?.message ?? d?.detail ?? `خطأ ${this.status}`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, 'مش قادر أوصل للسيرفر');
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : body;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const api = {
  listBoards: () => request<BoardSummary[]>('/api/boards'),

  createBoard: (payload: { name: string; color?: string; doc?: SceneDoc }) =>
    request<Board>('/api/boards', { method: 'POST', body: JSON.stringify(payload) }),

  getBoard: (id: string) => request<Board>(`/api/boards/${id}`),

  patchBoard: (
    id: string,
    payload: {
      name?: string;
      color?: string;
      doc?: SceneDoc;
      thumb?: string;
      version?: number;
    },
  ) => request<Board>(`/api/boards/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  deleteBoard: (id: string) => request<void>(`/api/boards/${id}`, { method: 'DELETE' }),

  share: (id: string) => request<ShareInfo>(`/api/boards/${id}/share`, { method: 'POST' }),

  unshare: (id: string) => request<void>(`/api/boards/${id}/share`, { method: 'DELETE' }),

  getShared: (token: string) => request<Board>(`/api/shared/${token}`),
};
