const TZ = 'Asia/Manila';

const dateFmt = new Intl.DateTimeFormat('en-PH', { timeZone: TZ, month: 'short', day: 'numeric', year: 'numeric' });
const dateShort = new Intl.DateTimeFormat('en-PH', { timeZone: TZ, month: 'short', day: 'numeric' });
const timeFmt = new Intl.DateTimeFormat('en-PH', { timeZone: TZ, hour: 'numeric', minute: '2-digit' });
const dtFmt = new Intl.DateTimeFormat('en-PH', {
  timeZone: TZ, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
});

const sec = (ts) => (ts > 1e12 ? ts : ts * 1000);

export const fmtDate = (ts) => (ts ? dateFmt.format(sec(ts)) : '—');
export const fmtDay = (ts) => (ts ? dateShort.format(sec(ts)) : '—');
export const fmtTime = (ts) => (ts ? timeFmt.format(sec(ts)) : '—');
export const fmtDateTime = (ts) => (ts ? dtFmt.format(sec(ts)) : '—');

export function fmtNum(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return Number(value).toFixed(digits);
}

export function fmtPct(value, digits = 0) {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtAgo(ts) {
  if (!ts) return 'never';
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 45) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export const SOURCE_LABEL = {
  'probe-serial': 'Probe (USB)',
  'probe-http': 'Probe (network)',
  simulated: 'Simulated',
  seed: 'Demo data',
};

export function isSynthetic(source) {
  return source === 'simulated' || source === 'seed';
}

/** Local date+time string for <input type="datetime-local"> in Philippine time. */
export function toLocalInput(ts) {
  const d = new Date(sec(ts) + 8 * 3600 * 1000);
  return d.toISOString().slice(0, 16);
}

export function fromLocalInput(value) {
  if (!value) return null;
  return Date.parse(`${value}:00+08:00`) / 1000;
}
