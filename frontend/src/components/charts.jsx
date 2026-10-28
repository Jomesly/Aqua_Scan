import { useEffect, useMemo, useRef, useState } from 'react';
import { fmtDateTime, fmtNum, fmtTime, fmtDay } from '../lib/format';

function useWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

function niceTicks(min, max, count = 5) {
  const span = max - min || 1;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(Number(v.toFixed(6)));
  return ticks;
}

/** Shared keyboard/pointer inspection over an array of x positions. */
function useInspect(xs) {
  const [idx, setIdx] = useState(null);
  const onMove = (e, toLocalX) => {
    const x = toLocalX(e);
    let best = 0;
    let bestD = Infinity;
    xs.forEach((px, i) => {
      const d = Math.abs(px - x);
      if (d < bestD) { bestD = d; best = i; }
    });
    setIdx(best);
  };
  const onKey = (e) => {
    if (!xs.length) return;
    if (e.key === 'ArrowRight') { setIdx((i) => Math.min(xs.length - 1, (i ?? -1) + 1)); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { setIdx((i) => Math.max(0, (i ?? xs.length) - 1)); e.preventDefault(); }
    if (e.key === 'Home') { setIdx(0); e.preventDefault(); }
    if (e.key === 'End') { setIdx(xs.length - 1); e.preventDefault(); }
    if (e.key === 'Escape') setIdx(null);
  };
  return { idx, setIdx, onMove, onKey };
}

export function TemperatureChart({ points, band, height = 260, hours = 24 }) {
  const [ref, width] = useWidth();
  const pad = { l: 40, r: 12, t: 14, b: 28 };
  const w = width;
  const h = height;

  const model = useMemo(() => {
    if (!points?.length) return null;
    const ts = points.map((p) => p.ts);
    const vals = points.flatMap((p) => [p.min_c ?? p.temperature_c, p.max_c ?? p.temperature_c]);
    const lo = Math.min(...vals, band.min_c - 1);
    const hi = Math.max(...vals, band.max_c + 1);
    const x0 = Math.min(...ts);
    const x1 = Math.max(...ts, x0 + 1);
    const sx = (t) => pad.l + ((t - x0) / (x1 - x0)) * (w - pad.l - pad.r);
    const sy = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * (h - pad.t - pad.b);
    return { lo, hi, x0, x1, sx, sy };
  }, [points, band, w, h]);

  const xs = useMemo(() => (model ? points.map((p) => model.sx(p.ts)) : []), [model, points]);
  const { idx, setIdx, onMove, onKey } = useInspect(xs);

  if (!model) return <div ref={ref} className="empty small">No readings in this period.</div>;
  const { sx, sy, lo, hi, x0, x1 } = model;

  const line = points.map((p, i) => `${i ? 'L' : 'M'}${sx(p.ts).toFixed(1)},${sy(p.temperature_c).toFixed(1)}`).join('');
  const area = points.length > 1
    ? `${points.map((p, i) => `${i ? 'L' : 'M'}${sx(p.ts).toFixed(1)},${sy(p.max_c).toFixed(1)}`).join('')}`
      + `${[...points].reverse().map((p) => `L${sx(p.ts).toFixed(1)},${sy(p.min_c).toFixed(1)}`).join('')}Z`
    : '';
  const out = points.filter((p) => p.temperature_c < band.min_c || p.temperature_c > band.max_c);
  const yTicks = niceTicks(lo, hi, 5);
  const xCount = Math.max(2, Math.floor((w - pad.l) / 110));
  const xTicks = Array.from({ length: xCount }, (_, i) => x0 + ((x1 - x0) * i) / (xCount - 1));
  const fmtX = hours > 48 ? fmtDay : fmtTime;
  const sel = idx != null ? points[idx] : null;

  const toLocalX = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    return ((clientX - rect.left) / rect.width) * w;
  };

  const summary = `Water temperature over the last ${hours} hours: ${points.length} points, `
    + `range ${fmtNum(Math.min(...points.map((p) => p.min_c)))} to ${fmtNum(Math.max(...points.map((p) => p.max_c)))} °C. `
    + `${out.length} points outside the ${band.min_c}–${band.max_c} °C band. Use arrow keys to inspect values.`;

  return (
    <div ref={ref} className="chart-box">
      <svg
        className="chart"
        width={w}
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        role="img"
        aria-label={summary}
        tabIndex={0}
        onKeyDown={onKey}
        onMouseMove={(e) => onMove(e, toLocalX)}
        onTouchMove={(e) => onMove(e, toLocalX)}
        onMouseLeave={() => setIdx(null)}
        onBlur={() => setIdx(null)}
      >
        <rect className="band" x={pad.l} width={w - pad.l - pad.r} y={sy(band.max_c)} height={sy(band.min_c) - sy(band.max_c)} />
        <line className="band-edge" x1={pad.l} x2={w - pad.r} y1={sy(band.max_c)} y2={sy(band.max_c)} />
        <line className="band-edge" x1={pad.l} x2={w - pad.r} y1={sy(band.min_c)} y2={sy(band.min_c)} />
        {yTicks.map((v) => (
          <g key={v}>
            <line className="grid-line" x1={pad.l} x2={w - pad.r} y1={sy(v)} y2={sy(v)} opacity={0.6} />
            <text x={pad.l - 8} y={sy(v) + 4} textAnchor="end">{v}°</text>
          </g>
        ))}
        {xTicks.map((t, i) => (
          <text key={t} x={sx(t)} y={h - 8} textAnchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}>{fmtX(t)}</text>
        ))}
        {area && <path className="range" d={area} />}
        <path className="line" d={line} />
        {out.map((p) => {
          const x = sx(p.ts);
          const y = sy(p.temperature_c);
          const up = p.temperature_c > band.max_c;
          return (
            <path key={p.ts} className="out-marker" d={up ? `M${x},${y - 6}L${x + 5},${y + 3}L${x - 5},${y + 3}Z` : `M${x},${y + 6}L${x + 5},${y - 3}L${x - 5},${y - 3}Z`} />
          );
        })}
        {sel && (
          <g>
            <line className="cursor" x1={sx(sel.ts)} x2={sx(sel.ts)} y1={pad.t} y2={h - pad.b} />
            <circle className="dot" cx={sx(sel.ts)} cy={sy(sel.temperature_c)} r={5} />
          </g>
        )}
      </svg>
      {sel && (
        <div className="chart-tip" style={{ left: `${(sx(sel.ts) / w) * 100}%`, top: sy(sel.temperature_c) }} aria-live="polite">
          {fmtNum(sel.temperature_c)} °C · {fmtDateTime(sel.ts)}
          {sel.synthetic ? ' · demo' : ''}
        </div>
      )}
    </div>
  );
}

export function GrowthChart({ rounds, poly, target, height = 260 }) {
  const [ref, width] = useWidth();
  const pad = { l: 48, r: 16, t: 14, b: 32 };
  const w = width;
  const h = height;
  const xs0 = rounds.map((r) => r.doc);
  const ys0 = rounds.map((r) => r.mean_weight_g);
  const model = useMemo(() => {
    if (!rounds.length) return null;
    const xLo = Math.min(...xs0) - 5;
    const xHi = Math.max(...xs0) + 5;
    const yHi = Math.max(...ys0, target) * 1.12;
    const sx = (d) => pad.l + ((d - xLo) / (xHi - xLo || 1)) * (w - pad.l - pad.r);
    const sy = (v) => pad.t + (1 - v / yHi) * (h - pad.t - pad.b);
    return { xLo, xHi, yHi, sx, sy };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rounds, target, w, h]);
  const xs = useMemo(() => (model ? rounds.map((r) => model.sx(r.doc)) : []), [model, rounds]);
  const { idx, setIdx, onMove, onKey } = useInspect(xs);

  if (!model) return <div ref={ref} className="empty small">No sampling rounds yet.</div>;
  const { sx, sy, xLo, xHi, yHi } = model;
  const toLocalX = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    return ((e.clientX - rect.left) / rect.width) * w;
  };
  const sel = idx != null ? rounds[idx] : null;
  const curve = poly?.curve?.map(([d, v], i) => `${i ? 'L' : 'M'}${sx(d).toFixed(1)},${sy(v).toFixed(1)}`).join('');
  const obs = rounds.map((r, i) => `${i ? 'L' : 'M'}${sx(r.doc).toFixed(1)},${sy(r.mean_weight_g).toFixed(1)}`).join('');

  return (
    <div ref={ref} className="chart-box">
      <svg
        className="chart" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" tabIndex={0}
        aria-label={`Mean fish weight by days of culture over ${rounds.length} sampling rounds; target ${target} g. Use arrow keys to inspect.`}
        onKeyDown={onKey} onMouseMove={(e) => onMove(e, toLocalX)} onMouseLeave={() => setIdx(null)} onBlur={() => setIdx(null)}
      >
        {niceTicks(0, yHi, 5).map((v) => (
          <g key={v}>
            <line className="grid-line" x1={pad.l} x2={w - pad.r} y1={sy(v)} y2={sy(v)} />
            <text x={pad.l - 8} y={sy(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        {niceTicks(xLo, xHi, 6).map((d) => (
          <text key={d} x={sx(d)} y={h - 10} textAnchor="middle">{d}</text>
        ))}
        <line className="target" x1={pad.l} x2={w - pad.r} y1={sy(target)} y2={sy(target)} />
        <text x={pad.l + 6} y={sy(target) - 6} textAnchor="start" style={{ fill: "var(--accent)" }}>target {target} g</text>
        {curve && <path className="poly" d={curve} />}
        <path className="line" d={obs} opacity={curve ? 0.35 : 1} />
        {rounds.map((r) => (
          <circle key={r.id} className="dot" cx={sx(r.doc)} cy={sy(r.mean_weight_g)} r={4.5} />
        ))}
        {sel && <line className="cursor" x1={sx(sel.doc)} x2={sx(sel.doc)} y1={pad.t} y2={h - pad.b} />}
      </svg>
      {sel && (
        <div className="chart-tip" style={{ left: `${(sx(sel.doc) / w) * 100}%`, top: sy(sel.mean_weight_g) }}>
          Day {fmtNum(sel.doc, 0)} · {fmtNum(sel.mean_weight_g, 0)} g · n={sel.n}
        </div>
      )}
    </div>
  );
}

const SHAPES = ['circle', 'square', 'diamond', 'triangle'];

function Shape({ kind, x, y, r = 5 }) {
  if (kind === 'square') return <rect x={x - r} y={y - r} width={r * 2} height={r * 2} className="dot" />;
  if (kind === 'diamond') return <path d={`M${x},${y - r - 1}L${x + r + 1},${y}L${x},${y + r + 1}L${x - r - 1},${y}Z`} className="dot" />;
  if (kind === 'triangle') return <path d={`M${x},${y - r - 1}L${x + r + 1},${y + r}L${x - r - 1},${y + r}Z`} className="dot" />;
  return <circle cx={x} cy={y} r={r} className="dot" />;
}

export function ScatterChart({ points, xLabel, yLabel, groupLabel = (g) => `Pond ${g}`, height = 240 }) {
  const [ref, width] = useWidth();
  const pad = { l: 44, r: 14, t: 12, b: 38 };
  const w = width;
  const h = height;
  if (!points?.length) return <div ref={ref} className="empty small">No data points yet.</div>;
  const xsV = points.map((p) => p.x);
  const ysV = points.map((p) => p.y);
  const xHi = Math.max(...xsV, 1) * 1.08;
  const yLo = Math.min(...ysV) - 0.2;
  const yHi = Math.max(...ysV) + 0.2;
  const sx = (v) => pad.l + (v / xHi) * (w - pad.l - pad.r);
  const sy = (v) => pad.t + (1 - (v - yLo) / (yHi - yLo || 1)) * (h - pad.t - pad.b);
  const groups = [...new Set(points.map((p) => p.pond_id))];
  return (
    <div ref={ref} className="chart-box">
      <svg className="chart" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img"
        aria-label={`Scatter of ${yLabel} against ${xLabel}, ${points.length} sampling rounds.`}>
        {niceTicks(yLo, yHi, 4).map((v) => (
          <g key={v}>
            <line className="grid-line" x1={pad.l} x2={w - pad.r} y1={sy(v)} y2={sy(v)} />
            <text x={pad.l - 8} y={sy(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        {niceTicks(0, xHi, 5).map((v) => (
          <text key={v} x={sx(v)} y={h - 20} textAnchor="middle">{v}</text>
        ))}
        <text x={(w + pad.l) / 2} y={h - 4} textAnchor="middle">{xLabel}</text>
        {points.map((p, i) => (
          <Shape key={i} kind={SHAPES[groups.indexOf(p.pond_id) % SHAPES.length]} x={sx(p.x)} y={sy(p.y)} />
        ))}
      </svg>
      <div className="legend" style={{ marginTop: 6 }}>
        {groups.map((g, i) => (
          <span key={g}>
            <svg width="14" height="14" aria-hidden="true" className="chart"><Shape kind={SHAPES[i % SHAPES.length]} x={7} y={7} r={4} /></svg>
            {groupLabel(g)}
          </span>
        ))}
        <span>y: {yLabel}</span>
      </div>
    </div>
  );
}
