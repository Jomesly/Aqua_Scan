import { useEffect, useMemo, useRef, useState } from 'react';
import { fmtNum } from '../lib/format';

function useWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(640);
  useEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(260, entry.contentRect.width)));
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

function useInspect(xs) {
  const [idx, setIdx] = useState(null);
  const onMove = (e, w) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * w;
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
    if (e.key === 'Escape') setIdx(null);
  };
  return { idx, setIdx, onMove, onKey };
}

/** Average weight per sampling round, with the degree-2 growth curve when available. */
export function GrowthChart({ points, poly, target, height = 260 }) {
  const [ref, w] = useWidth();
  const h = height;
  const pad = { l: 48, r: 16, t: 14, b: 34 };
  const model = useMemo(() => {
    if (!points.length) return null;
    const xs0 = points.map((p) => p.doc);
    const ys0 = points.map((p) => p.avg);
    const xLo = Math.max(0, Math.min(...xs0) - 8);
    const xHi = Math.max(...xs0) + 8;
    const yHi = Math.max(...ys0, target || 0) * 1.12;
    const sx = (d) => pad.l + ((d - xLo) / (xHi - xLo || 1)) * (w - pad.l - pad.r);
    const sy = (v) => pad.t + (1 - v / yHi) * (h - pad.t - pad.b);
    return { xLo, xHi, yHi, sx, sy };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, target, w, h]);
  const xs = useMemo(() => (model ? points.map((p) => model.sx(p.doc)) : []), [model, points]);
  const { idx, setIdx, onMove, onKey } = useInspect(xs);
  if (!model) return <div ref={ref} className="empty small">No completed sampling rounds yet.</div>;
  const { sx, sy, xLo, xHi, yHi } = model;
  const sel = idx != null ? points[idx] : null;
  const curve = poly?.curve?.map(([d, v], i) => `${i ? 'L' : 'M'}${sx(d).toFixed(1)},${sy(v).toFixed(1)}`).join('');
  const obs = points.map((p, i) => `${i ? 'L' : 'M'}${sx(p.doc).toFixed(1)},${sy(p.avg).toFixed(1)}`).join('');
  return (
    <div ref={ref} className="chart-box">
      <svg className="chart" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" tabIndex={0}
        aria-label={`Average fish weight by days of culture over ${points.length} rounds; target ${target} g. Arrow keys inspect.`}
        onKeyDown={onKey} onMouseMove={(e) => onMove(e, w)} onMouseLeave={() => setIdx(null)} onBlur={() => setIdx(null)}>
        {niceTicks(0, yHi, 5).map((v) => (
          <g key={v}>
            <line className="grid-line" x1={pad.l} x2={w - pad.r} y1={sy(v)} y2={sy(v)} />
            <text x={pad.l - 8} y={sy(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        {niceTicks(xLo, xHi, 6).map((d) => <text key={d} x={sx(d)} y={h - 14} textAnchor="middle">{d}</text>)}
        <text x={(w + pad.l) / 2} y={h - 1} textAnchor="middle">days of culture</text>
        <text x={12} y={pad.t + 2} textAnchor="start">g</text>
        {target ? (
          <>
            <line className="target" x1={pad.l} x2={w - pad.r} y1={sy(target)} y2={sy(target)} />
            <text x={pad.l + 6} y={sy(target) - 6} style={{ fill: 'var(--accent)' }}>target {target} g</text>
          </>
        ) : null}
        {curve && <path className="poly" d={curve} />}
        <path className="line" d={obs} opacity={curve ? 0.35 : 1} />
        {points.map((p) => <circle key={p.round_id ?? p.doc} className="dot" cx={sx(p.doc)} cy={sy(p.avg)} r={4.5} />)}
        {sel && <line className="cursor" x1={sx(sel.doc)} x2={sx(sel.doc)} y1={pad.t} y2={h - pad.b} />}
      </svg>
      {sel && (
        <div className="chart-tip" style={{ left: `${(sx(sel.doc) / w) * 100}%`, top: sy(sel.avg) }}>
          Day {fmtNum(sel.doc, 0)} · {fmtNum(sel.avg, 0)} g
        </div>
      )}
      <div className="legend">
        <span><i className="dot" />Average weight per round</span>
        {curve && <span><i className="dash" />Degree-2 growth curve (observed days only)</span>}
        {target ? <span><i className="dash accent" />Target size</span> : null}
      </div>
    </div>
  );
}

const SERIES_COLORS = ['var(--chart-line)', 'var(--accent)', 'var(--info)', 'var(--critical)'];

/** Multi-series line chart, e.g. precision / recall / mAP over training epochs. */
export function LineChart({ rows, x, series, yMax = 1, height = 240, xLabel }) {
  const [ref, w] = useWidth();
  const h = height;
  const pad = { l: 40, r: 14, t: 12, b: 34 };
  const xsV = rows.map((r) => r[x]);
  const xLo = Math.min(...xsV);
  const xHi = Math.max(...xsV);
  const sx = (v) => pad.l + ((v - xLo) / (xHi - xLo || 1)) * (w - pad.l - pad.r);
  const sy = (v) => pad.t + (1 - v / yMax) * (h - pad.t - pad.b);
  const xs = rows.map((r) => sx(r[x]));
  const { idx, setIdx, onMove, onKey } = useInspect(xs);
  const sel = idx != null ? rows[idx] : null;
  return (
    <div ref={ref} className="chart-box">
      <svg className="chart" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" tabIndex={0}
        aria-label={`${series.map((s) => s.label).join(', ')} by ${xLabel}. Arrow keys inspect.`}
        onKeyDown={onKey} onMouseMove={(e) => onMove(e, w)} onMouseLeave={() => setIdx(null)} onBlur={() => setIdx(null)}>
        {niceTicks(0, yMax, 4).map((v) => (
          <g key={v}>
            <line className="grid-line" x1={pad.l} x2={w - pad.r} y1={sy(v)} y2={sy(v)} />
            <text x={pad.l - 6} y={sy(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        {niceTicks(xLo, xHi, 6).map((v) => <text key={v} x={sx(v)} y={h - 14} textAnchor="middle">{v}</text>)}
        <text x={(w + pad.l) / 2} y={h - 1} textAnchor="middle">{xLabel}</text>
        {series.map((s, i) => (
          <path key={s.key} fill="none" strokeWidth={2} stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
            strokeDasharray={i % 2 ? '6 4' : undefined}
            d={rows.map((r, j) => `${j ? 'L' : 'M'}${sx(r[x]).toFixed(1)},${sy(r[s.key]).toFixed(1)}`).join('')} />
        ))}
        {sel && <line className="cursor" x1={sx(sel[x])} x2={sx(sel[x])} y1={pad.t} y2={h - pad.b} />}
      </svg>
      {sel && (
        <div className="chart-tip" style={{ left: `${(sx(sel[x]) / w) * 100}%`, top: pad.t + 8 }}>
          {xLabel} {sel[x]} · {series.map((s) => `${s.label} ${fmtNum(sel[s.key], 3)}`).join(' · ')}
        </div>
      )}
      <div className="legend">
        {series.map((s, i) => (
          <span key={s.key}>
            <i className="swatch" style={{ borderTopColor: SERIES_COLORS[i % SERIES_COLORS.length],
              borderTopStyle: i % 2 ? 'dashed' : 'solid' }} />{s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Estimate vs reference with the 1:1 line (e.g. estimated vs scale weight). */
export function AgreementScatter({ points, xLabel, yLabel, height = 260 }) {
  const [ref, w] = useWidth();
  const h = height;
  const pad = { l: 46, r: 14, t: 12, b: 36 };
  if (!points.length) return <div ref={ref} className="empty small">No paired measurements yet.</div>;
  const hi = Math.max(...points.flatMap((p) => [p.x, p.y])) * 1.08;
  const sx = (v) => pad.l + (v / hi) * (w - pad.l - pad.r);
  const sy = (v) => pad.t + (1 - v / hi) * (h - pad.t - pad.b);
  return (
    <div ref={ref} className="chart-box">
      <svg className="chart" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img"
        aria-label={`${yLabel} against ${xLabel}, ${points.length} fish, with the 1 to 1 line.`}>
        {niceTicks(0, hi, 5).map((v) => (
          <g key={v}>
            <line className="grid-line" x1={pad.l} x2={w - pad.r} y1={sy(v)} y2={sy(v)} />
            <text x={pad.l - 6} y={sy(v) + 4} textAnchor="end">{v}</text>
            <text x={sx(v)} y={h - 16} textAnchor="middle">{v}</text>
          </g>
        ))}
        <text x={(w + pad.l) / 2} y={h - 2} textAnchor="middle">{xLabel}</text>
        <line className="target" x1={sx(0)} y1={sy(0)} x2={sx(hi)} y2={sy(hi)} />
        {points.map((p, i) => <circle key={i} className={`dot ${p.demo ? 'demo' : ''}`} cx={sx(p.x)} cy={sy(p.y)} r={3.5} />)}
      </svg>
      <div className="legend"><span><i className="dot" />{yLabel} (y) vs {xLabel} (x)</span><span><i className="dash accent" />1:1 line</span></div>
    </div>
  );
}
