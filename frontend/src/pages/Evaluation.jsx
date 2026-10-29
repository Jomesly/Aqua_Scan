import { useState } from 'react';
import { Download, FlaskConical, Scale, Stethoscope, Target } from 'lucide-react';
import { Card, LoadError, Loading, Notice, Stat } from '../components/ui';
import { LineChart } from '../components/charts';
import { useResource } from '../lib/api';
import { fmtNum, fmtPct } from '../lib/format';

function Confusion({ m, rowLabel = 'System', colLabel = 'Technician' }) {
  if (!m?.n) return <p className="muted small">No paired assessments yet.</p>;
  return (
    <div className="table-wrap">
      <table className="confusion">
        <caption className="sr-only">Rows: {rowLabel}. Columns: {colLabel}.</caption>
        <thead>
          <tr><th scope="col">{rowLabel} ↓ / {colLabel} →</th>{m.labels.map((l) => <th key={l} scope="col">{l}</th>)}</tr>
        </thead>
        <tbody>
          {m.matrix.map((row, i) => (
            <tr key={m.labels[i]}>
              <th scope="row">{m.labels[i]}</th>
              {row.map((v, j) => <td key={j} className={i === j ? 'diag' : ''}>{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Table10({ t }) {
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>Metric</th>{t.models.map((m) => <th key={m} className="num">{m}{m === 'YOLOv8s' && <span className="tag">deployed</span>}</th>)}</tr></thead>
        <tbody>
          {t.rows.map(([label, vals, better]) => {
            const best = better === 'min' ? Math.min(...vals) : Math.max(...vals);
            return (
              <tr key={label}>
                <td>{label}</td>
                {vals.map((v, i) => <td key={i} className={`num ${v === best ? 'best' : ''}`}>{v}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ErrorStat({ label, e, unit }) {
  return (
    <div className="stats three">
      <Stat label={`${label} MAE`} value={fmtNum(e?.mae, 2)} unit={unit} />
      <Stat label="RMSE" value={fmtNum(e?.rmse, 2)} unit={unit} />
      <Stat label="MARE" value={e?.mare != null ? fmtNum(e.mare, 1) : '—'} unit="%" title={`${e?.n ?? 0} fish`} />
    </div>
  );
}

function WeightModelTable({ fit }) {
  if (!fit) return <p className="muted small">No fitted model yet. The administrator fits it in Maintenance once enough fish have scale weights.</p>;
  const rows = ['linear', 'poly'].map((k) => ({ key: k, ...fit[k] }));
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>Model</th><th>Terms kept</th><th className="num">R²</th><th className="num">RMSE g</th><th className="num">MAE g</th>
          <th className="num">MARE %</th><th className="num">MXAE g</th><th className="num">MXRE %</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td>{r.label}{fit.selected === r.key && <span className="tag good">selected</span>}</td>
              <td className="mono xs">{r.terms.join(', ')}</td>
              <td className="num">{fmtNum(r.cv.r2, 3)}</td><td className="num">{fmtNum(r.cv.rmse, 1)}</td>
              <td className="num">{fmtNum(r.cv.mae, 1)}</td><td className="num">{fmtNum(r.cv.mare, 1)}</td>
              <td className="num">{fmtNum(r.cv.mxae, 1)}</td><td className="num">{fmtNum(r.cv.mxre, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="subtle card-pad">Cross-validated ({fit.cv_scheme}) on {fit.n} fish. The degree-2 model is kept only if it lowers the validation RMSE by at least 5 %.</p>
    </div>
  );
}

export default function Evaluation() {
  const [demo, setDemo] = useState(true);
  const { data, error, loading, reload } = useResource(`/api/evaluation?include_demo=${demo}`, { deps: [demo] });
  if (loading && !data) return <Loading />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;
  const b = data.benchmarks;

  return (
    <div className="stack">
      <div className="page-head row-between wrap">
        <div>
          <span className="eyebrow">Evaluation</span>
          <h1>How well does Tilapiers agree with the references?</h1>
          <p>Detector benchmarks, weight-model accuracy against the facility scale, and status agreement with the technician.</p>
        </div>
        <div className="page-actions">
          <a className="btn" href="/api/export/fish.csv"><Download size={18} aria-hidden="true" />Fish CSV</a>
          <a className="btn" href="/api/export/rounds.csv"><Download size={18} aria-hidden="true" />Rounds CSV</a>
        </div>
      </div>
      <label className="toggle">
        <input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} />
        Include demo data ({data.demo_rounds} of {data.rounds_used} completed rounds are demo data)
      </label>

      <Card title="Disease screening detector" icon={FlaskConical}
        hint="Paper Table 10: three YOLO versions, small scale, same deduplicated split of the public dataset.">
        <Table10 t={b.table10} />
        <p className="subtle card-pad">{b.table10.note} Best value in each row is highlighted.</p>
        <h3 className="sub">Weighted scores (paper Table 11)</h3>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Weighting (P / R / mAP50 / CPU)</th>{b.table11.models.map((m) => <th key={m} className="num">{m}</th>)}</tr></thead>
            <tbody>
              {b.table11.rows.map(([label, vals]) => (
                <tr key={label}><td>{label}</td>{vals.map((v, i) => <td key={i} className={`num ${v === Math.max(...vals) ? 'best' : ''}`}>{v}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
        <Notice kind="info">Deployed screening model: <strong>{b.deployed?.name}</strong>
          {b.deployed?.available ? ` (${b.deployed.classes.join(', ')})` : `, unavailable: ${b.deployed?.error}`}.
          Red sores is the weakest flag (AP50 0.30, trained as Aeromonas). More red-sore photos checked by the technician are the first improvement.</Notice>
      </Card>

      {b.curve && (
        <Card title="YOLOv8s training run" hint={`100 epochs. Final epoch: precision ${fmtNum(b.final_epoch.precision, 3)}, recall ${fmtNum(b.final_epoch.recall, 3)}, mAP50 ${fmtNum(b.final_epoch.map50, 3)}, mAP50-95 ${fmtNum(b.final_epoch.map50_95, 3)} (validation split).`}>
          <LineChart rows={b.curve} x="epoch" xLabel="epoch"
            series={[{ key: 'precision', label: 'Precision' }, { key: 'recall', label: 'Recall' },
              { key: 'map50', label: 'mAP50' }, { key: 'map50_95', label: 'mAP50-95' }]} />
          <div className="bench-images">
            {b.images.map((n) => (
              <a key={n} href={`/api/benchmarks/${n}`} target="_blank" rel="noreferrer">
                <img src={`/api/benchmarks/${n}`} alt={n.replace(/[_.]/g, ' ')} loading="lazy" />
                <span className="xs">{n.replace(/\.(png|jpg)$/, '').replace(/_/g, ' ')}</span>
              </a>
            ))}
          </div>
        </Card>
      )}

      <Card title="Screening vs technician" icon={Stethoscope} hint={`${data.screening.n_reviewed} fish checked by the technician. Only checked fish count. Fish checked from the review queue were flagged by the system, so also check a sample of Normal fish on each round's page to measure missed defects.`}>
        <div className="stats three">
          <Stat label="Accuracy (3 classes)" value={fmtPct(data.screening.accuracy, 1)} />
          <Stat label="Recall of Refer (fish)" value={fmtPct(data.screening.fish_refer_recall, 1)} title="Share of fish the technician saw a defect on that the system referred" />
          <Stat label="Other / not screened" value={data.screening.other_or_unscreened} />
        </div>
        <Confusion m={data.screening} rowLabel="Screening" />
      </Card>

      <div className="grid-2">
        <Card title="Health status agreement" icon={Target} hint="Pond Health status vs the technician's independent assessment">
          <div className="stats three">
            <Stat label="Exact agreement" value={fmtPct(data.health.accuracy, 1)} />
            <Stat label="Weighted κ" value={fmtNum(data.health.kappa_w, 3)} />
            <Stat label="Refer recall" value={fmtPct(data.health.refer_recall, 1)} />
          </div>
          <Confusion m={data.health} />
        </Card>
        <Card title="Harvest readiness agreement" icon={Target} hint="“Size reached, health review” is compared as Approaching">
          <div className="stats three">
            <Stat label="Exact agreement" value={fmtPct(data.readiness.accuracy, 1)} />
            <Stat label="Weighted κ" value={fmtNum(data.readiness.kappa_w, 3)} />
            <Stat label="Rounds" value={data.readiness.n} />
          </div>
          <Confusion m={data.readiness} />
        </Card>
      </div>

      <Card title="Weight estimation" icon={Scale} hint="Paper Table 12 format, filled with the current fit">
        <WeightModelTable fit={data.weight_model.last_fit} />
        <ErrorStat label="Length vs ruler:" e={data.length_error} unit="cm" />
        <ErrorStat label="Weight vs scale:" e={data.weight_error} unit="g" />
        <ErrorStat label="Average weight per round:" e={data.avg_weight_error} unit="g" />
      </Card>

      <Card title="Image-quality retake rate" hint="Share of uploaded photographs that failed the check and had to be retaken">
        <div className="stats three">
          <Stat label="Retake rate" value={fmtPct(data.retakes.rate, 1)} />
          <Stat label="Failed" value={data.retakes.failed} />
          <Stat label="Uploaded" value={data.retakes.total} />
        </div>
      </Card>
    </div>
  );
}
