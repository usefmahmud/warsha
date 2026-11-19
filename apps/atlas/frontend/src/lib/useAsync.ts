import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  error: Error | null
  loading: boolean
}

/**
 * Minimal data-fetching hook: re-runs when `deps` change, keeps the previous
 * value visible while reloading (so the board does not flash empty), and drops
 * results from stale runs.
 */
export function useAsync<T>(loader: () => Promise<T>, deps: readonly unknown[]): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: true })
  const [nonce, setNonce] = useState(0)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  useEffect(() => {
    let alive = true
    setState((prev) => ({ ...prev, loading: true, error: null }))
    loaderRef.current().then(
      (data) => {
        if (alive) setState({ data, error: null, loading: false })
      },
      (err: unknown) => {
        if (alive) setState((prev) => ({ ...prev, error: err as Error, loading: false }))
      },
    )
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { ...state, reload }
}
