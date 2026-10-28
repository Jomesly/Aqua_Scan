import { useState } from 'react';
import { Download, FlaskConical, Ruler, Scale, Sigma, Thermometer, Users, Waves } from 'lucide-react';
import { api, useResource } from '../lib/api';
import { fmtDateTime, fmtNum, fmtPct } from '../lib/format';
import { Button, Card, Field, LoadError, Loading, Notice, Stat, useToast } from '../components/ui';
import { ScatterChart } from '../components/charts';

function Metric({ m, label }) {
  if (!m) return <span className="subtle">—</span>;
  return (
    <span className="mono small">
      {label ? `${label} ` : ''}R² {fmtNum(m.r2, 3)} · RMSE {fmtNum(m.rmse, 3)} · MAE {fmtNum(m.mae, 3)}
    </span>
  );
}

function FciSection({ ev, onChange }) {
  const [poly, setPoly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const toast = useToast();
  const model = ev.fci_model;
  const fitted = model.name === 'fitted';
  const maxR2 = Math.max(0.01, ...ev.feature_groups.map((g) => g.cv?.r2 || 0));

  const fit = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.post('/api/evaluation/fit', { poly_features: poly ? ['condition_factor'] : [] });
      toast('Model fitted and applied to all fish');
      onChange();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };
  const reset = async () => {
    await api.post('/api/evaluation/reset-model');
    toast('Reverted to the default coefficients');
    onChange();
  };

  return (
    <Card title="Fish Condition Index regression" icon={Sigma}
      hint="Multiple linear regression of the technician's condition score on image indicators and condition factor (degree-2 terms at most).">
      <div className="grid-2">
        <div className="stack">
          <div className="row">
            <span className={`tag ${fitted ? '' : 'warn'}`}>{fitted ? 'Fitted model in use' : 'Default coefficients in use'}</span>
            <span className="subtle">{model.source}</span>
          </div>
          {model.metrics && (
            <div className="stack" style={{ gap: 4 }}>
              <Metric m={model.metrics.train} label="Train" />
              <Metric m={model.metrics.cv} label={`CV (${model.metrics.cv.method}, ${model.metrics.cv.groups} groups)`} />
            </div>
          )}
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Term</th><th className="num">Coefficient</th></tr></thead>
              <tbody>
                <tr><td>Intercept</td><td className="num">{fmtNum(model.intercept, 3)}</td></tr>
                {Object.entries(model.coefs).map(([k, v]) => (
                  <tr key={k}><td>{ev.feature_labels[k.replace('^2', '')] || k}{k.endsWith('^2') ? ' (squared)' : ''}</td><td className="num">{fmtNum(v, 3)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="stack">
          <h3>What each indicator group adds</h3>
          <p className="subtle">Cross-validated R², grouped by pond so no pond is in both training and testing.</p>
          {ev.feature_groups.map((g) => (
            <div key={g.group} className="bar-row">
              <span>{g.label}</span>
              <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: `${Math.max(0, (g.cv?.r2 || 0) / maxR2) * 100}%` }} /></span>
              <span className="mono small" style={{ textAlign: 'right' }}>{g.cv ? fmtNum(g.cv.r2, 3) : '—'}</span>
            </div>
          ))}
          {ev.feature_groups[0]?.error && <p className="subtle">{ev.feature_groups[0].error}</p>}
          <p className="subtle">{ev.n_scored_fish} technician-scored fish available.</p>
          <label className="row small" style={{ minHeight: 44 }}>
            <input type="checkbox" checked={poly} onChange={(e) => setPoly(e.target.checked)} style={{ width: 20, height: 20 }} />
            Add a squared term for condition factor
          </label>
          {err && <Notice kind="error">{err}</Notice>}
          <div className="row">
            <Button className="primary" icon={FlaskConical} busy={busy} onClick={fit}>Fit model on scored fish</Button>
            {fitted && <Button onClick={reset}>Reset to default</Button>}
          </div>
        </div>
      </div>
    </Card>
  );
}

function CalibrationSection({ ev, onChange }) {
  const [probe, setProbe] = useState('');
  const [ref, setRef] = useState('');
  const [busy, setBusy] = useState(false);
  const c = ev.probe_calibration;
  const add = async (e) => {
    e.preventDefault();
    if (probe === '' || ref === '') return;
    setBusy(true);
    try {
      await api.post('/api/calibrations', { probe_c: Number(probe), reference_c: Number(ref) });
      setProbe('');
      setRef('');
      onChange();
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="Probe vs reference thermometer" icon={Thermometer} hint="Temperature probe error before and during deployment.">
      <div className="stats" style={{ marginBottom: 16 }}>
        <Stat label="Pairs" value={c.n} />
        <Stat label="MAE" value={fmtNum(c.mae, 2)} unit="°C" />
        <Stat label="Bias" value={fmtNum(c.bias, 2)} unit="°C" />
        <Stat label="RMSE" value={fmtNum(c.rmse, 2)} unit="°C" />
        <Stat label="Max error" value={fmtNum(c.max_abs, 2)} unit="°C" />
      </div>
      <form onSubmit={add} className="form-grid two" style={{ alignItems: 'end' }}>
        <Field label="Probe reading" htmlFor="cal-p">
          <div className="input-unit"><input id="cal-p" className="input" type="number" step="0.01" inputMode="decimal" value={probe} onChange={(e) => setProbe(e.target.value)} /><span>°C</span></div>
        </Field>
        <Field label="Reference thermometer" htmlFor="cal-r">
          <div className="input-unit"><input id="cal-r" className="input" type="number" step="0.01" inputMode="decimal" value={ref} onChange={(e) => setRef(e.target.value)} /><span>°C</span></div>
        </Field>
        <Button type="submit" busy={busy} disabled={probe === '' || ref === ''}>Add calibration pair</Button>
      </form>
      {c.rows.length > 0 && (
        <details className="disclosure" style={{ marginTop: 8 }}>
          <summary>Show recorded pairs</summary>
          <div className="table-wrap" style={{ maxHeight: 240 }}>
            <table className="data">
              <thead><tr><th>When</th><th className="num">Probe</th><th className="num">Reference</th><th className="num">Error</th></tr></thead>
              <tbody>
                {c.rows.map((r) => (
                  <tr key={r.id}><td>{fmtDateTime(r.ts)}</td><td className="num">{fmtNum(r.probe_c, 2)}</td><td className="num">{fmtNum(r.reference_c, 2)}</td><td className="num">{fmtNum(r.probe_c - r.reference_c, 2)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </Card>
  );
}

function Confusion({ a }) {
  if (!a.n) return <p className="subtle">No completed rounds with a technician assessment yet.</p>;
  return (
    <div className="table-wrap">
      <table className="confusion" aria-label="Confusion matrix: rows are technician, columns are system">
        <thead>
          <tr><th>Technician ↓ / System →</th>{a.labels.map((l) => <th key={l} scope="col">{l}</th>)}</tr>
        </thead>
        <tbody>
          {a.labels.map((t) => (
            <tr key={t}>
              <th scope="row">{t}</th>
              {a.labels.map((s) => <td key={s} className={s === t ? 'diag' : ''}>{a.confusion[t][s]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Evaluation() {
  const { data: ev, error, loading, reload } = useResource('/api/evaluation');
  const { data: ponds } = useResource('/api/ponds?include_archived=true');
  const pondName = (id) => ponds?.find((p) => p.id === id)?.name || `Pond ${id}`;
  if (loading && !ev) return <Loading label="Loading evaluation" />;
  if (error && !ev) return <LoadError error={error} onRetry={reload} />;
  const sa = ev.stress_association;
  const le = ev.length_error;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Evaluation</h1>
          <p>Model and system performance against technician assessments and reference measurements. All results are descriptive; no claims of statistical significance are made.</p>
        </div>
      </div>

      <FciSection ev={ev} onChange={reload} />

      <div className="grid-2">
        <Card title="Health status agreement" icon={Users} hint="System status vs technician's independent assessment, per completed round.">
          <div className="stats" style={{ marginBottom: 14 }}>
            <Stat label="Rounds" value={ev.health_agreement.n} />
            <Stat label="Agreement" value={fmtPct(ev.health_agreement.accuracy)} />
            <Stat label="Cohen's κ" value={fmtNum(ev.health_agreement.kappa, 2)} />
          </div>
          <Confusion a={ev.health_agreement} />
        </Card>
        <Card title="Harvest readiness agreement" icon={Waves} hint="'Size reached, health review' counts as not yet Ready.">
          <div className="stats" style={{ marginBottom: 14 }}>
            <Stat label="Rounds" value={ev.readiness_agreement.n} />
            <Stat label="Agreement" value={fmtPct(ev.readiness_agreement.accuracy)} />
            <Stat label="Cohen's κ" value={fmtNum(ev.readiness_agreement.kappa, 2)} />
          </div>
          <Confusion a={ev.readiness_agreement} />
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Environment and fish condition" icon={Scale}
          hint="Round mean FCI vs hours outside the temperature band since the previous round; pooled across ponds with pond as a grouping factor.">
          <div className="stats" style={{ marginBottom: 12 }}>
            <Stat label="Rounds" value={sa.n} />
            <Stat label="Ponds" value={sa.n_ponds} />
            <Stat label="Slope (FCI per h)" value={fmtNum(sa.slope, 4)} />
            <Stat label="R²" value={fmtNum(sa.r2, 3)} />
          </div>
          <ScatterChart points={sa.points || []} xLabel="hours outside band" yLabel="mean FCI" groupLabel={pondName} />
          <p className="subtle" style={{ marginTop: 8 }}>{sa.note}</p>
        </Card>
        <div className="grid" style={{ alignContent: 'start' }}>
          <Card title="Image length vs ruler" icon={Ruler}>
            <div className="stats">
              <Stat label="Fish" value={le.n} />
              <Stat label="MAE" value={fmtNum(le.mae, 2)} unit="cm" />
              <Stat label="Bias" value={fmtNum(le.bias, 2)} unit="cm" />
            </div>
            {le.n_stub_excluded > 0 && <p className="subtle" style={{ marginTop: 8 }}>{le.n_stub_excluded} measurement(s) from the placeholder detector excluded.</p>}
            {le.n === 0 && <p className="subtle" style={{ marginTop: 8 }}>Available once the trained YOLO26 model detects the reference scale.</p>}
          </Card>
          <CalibrationSection ev={ev} onChange={reload} />
        </div>
      </div>

      <Card title="Export data" icon={Download} hint="CSV files for analysis in a spreadsheet or statistics package. Demo and placeholder rows are labeled.">
        <div className="row">
          {[
            ['fish', 'Fish & indicators'], ['rounds', 'Sampling rounds'], ['temperature', 'Temperature log'],
            ['observations', 'Observations'], ['notifications', 'Alerts'],
          ].map(([key, label]) => (
            <a key={key} className="btn" href={`/api/export/${key}.csv`} download><Download size={16} aria-hidden="true" />{label}</a>
          ))}
        </div>
      </Card>
    </>
  );
}
