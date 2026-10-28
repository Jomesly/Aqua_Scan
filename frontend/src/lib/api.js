import { useCallback, useEffect, useRef, useState } from 'react';

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body, isForm = false) {
  const init = { method, cache: 'no-store', headers: {} };
  if (body !== undefined) {
    if (isForm) init.body = body;
    else {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError('Cannot reach the Tilapiers server. Check that the backend is running.', 0);
  }
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON */
  }
  if (!res.ok) {
    let detail = data?.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join('; ');
    throw new ApiError(detail || `Request failed (${res.status})`, res.status);
  }
  return data;
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b ?? {}),
  put: (p, b) => request('PUT', p, b),
  patch: (p, b) => request('PATCH', p, b),
  del: (p) => request('DELETE', p),
  form: (p, formData) => request('POST', p, formData, true),
};

/**
 * Fetch a resource and optionally re-poll it. Returns { data, error, loading, reload }.
 * Polling pauses while the tab is hidden.
 */
export function useResource(path, { interval = 0, deps = [] } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const alive = useRef(true);

  const reload = useCallback(async () => {
    if (!path) return;
    try {
      const data = await api.get(path);
      if (alive.current) setState({ data, error: null, loading: false });
    } catch (error) {
      if (alive.current) setState((s) => ({ ...s, error, loading: false }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);

  useEffect(() => {
    alive.current = true;
    setState((s) => ({ ...s, loading: true }));
    reload();
    if (!interval) return () => { alive.current = false; };
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') reload();
    }, interval);
    return () => {
      alive.current = false;
      clearInterval(id);
    };
  }, [reload, interval]);

  return { ...state, reload };
}
