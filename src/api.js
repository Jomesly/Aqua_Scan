import React from 'react';

const ENDPOINTS = {
  environment: '/api/environment',
  feeding: '/api/feeding/session',
  history: '/api/feeding/history?limit=25',
  alerts: '/api/alerts?limit=100',
  config: '/api/config',
  schedule: '/api/schedule',
  status: '/api/status',
};

async function getJSON(path) {
  const res = await fetch(path, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function postJSON(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const data = await res.json();
      detail = data.error || detail;
    } catch {
      /* keep status */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  saveConfig: (body) => postJSON('/api/config', body),
  testSession: () => postJSON('/api/admin/test-session'),
  exportUrl: (table) => `/api/export?table=${encodeURIComponent(table)}`,
  openLiveDashboard: () => window.open('http://127.0.0.1:8000/', '_blank', 'noopener,noreferrer'),
};

const EMPTY = {
  loading: true,
  error: null,
  environment: null,
  feeding: null,
  history: null,
  alerts: null,
  config: null,
  status: null,
};

/** Polls the FastAPI backend and returns [state, reload]. */
export function useTelemetry(intervalMs = 2000) {
  const [state, setState] = React.useState(EMPTY);
  const alive = React.useRef(true);

  const reload = React.useCallback(async () => {
    try {
      const [environment, feeding, history, alerts, config, status] =
        await Promise.all([
          getJSON(ENDPOINTS.environment),
          getJSON(ENDPOINTS.feeding),
          getJSON(ENDPOINTS.history),
          getJSON(ENDPOINTS.alerts),
          getJSON(ENDPOINTS.config),
          getJSON(ENDPOINTS.status),
        ]);
      if (!alive.current) return;
      setState({
        loading: false,
        error: null,
        environment,
        feeding,
        history,
        alerts,
        config,
        status,
      });
    } catch (error) {
      if (!alive.current) return;
      setState((prev) => ({ ...prev, loading: false, error: String(error.message || error) }));
    }
  }, []);

  React.useEffect(() => {
    alive.current = true;
    reload();
    const id = setInterval(reload, intervalMs);
    return () => {
      alive.current = false;
      clearInterval(id);
    };
  }, [reload, intervalMs]);

  return [state, reload];
}

/** A clock that ticks so countdowns stay live. */
export function useNow(intervalMs = 1000) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
