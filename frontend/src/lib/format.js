const TZ = 'Asia/Manila';

const dateFmt = new Intl.DateTimeFormat('en-PH', { timeZone: TZ, month: 'short', day: 'numeric', year: 'numeric' });
const dtFmt = new Intl.DateTimeFormat('en-PH', {
  timeZone: TZ, month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
});

const toMs = (v) => (typeof v === 'number' ? (v > 1e12 ? v : v * 1000) : Date.parse(v.length === 10 ? `${v}T00:00:00+08:00` : v));

/** Accepts epoch seconds or an ISO date string. */
export const fmtDate = (v) => (v ? dateFmt.format(toMs(v)) : '—');
export const fmtDateTime = (v) => (v ? dtFmt.format(toMs(v)) : '—');

export function fmtNum(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return Number(value).toFixed(digits);
}

export function fmtPct(value, digits = 0) {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export const todayIso = () => new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10);

export const SIGNS_LABEL = {
  none: 'No visible signs',
  aeromonas: 'Signs consistent with Aeromonas',
  tilv: 'Signs consistent with TiLV',
  other: 'Other signs',
};
