import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, Camera, ChevronRight, CloudSun, Droplets, Fish, History, Leaf, Thermometer, Waves,
} from 'lucide-react';
import { api, useResource } from '../lib/api';
import {
  fmtAgo, fmtDate, fmtDateTime, fmtDay, fmtNum, fmtPct, isSynthetic, SOURCE_LABEL,
} from '../lib/format';
import { Button, Card, Empty, Field, LoadError, Loading, Notice, Segmented, Stat, useToast } from '../components/ui';
import { EnvBadge, HealthBadge, ReadinessBadge } from '../components/Status';
import { GrowthChart, TemperatureChart } from '../components/charts';
import { Checklist } from './RoundDetail';

const TABS = [
  { id: 'environment', label: 'Environment', icon: Thermometer },
  { id: 'health', label: 'Fish health', icon: Fish },
  { id: 'harvest', label: 'Harvest', icon: Waves },
];

export default function Pond() {
  const { pondId } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'environment';
  const { data: pond, error, loading, reload } = useResource(`/api/ponds/${pondId}`, { interval: 10000 });

  if (loading && !pond) return <Loading label="Loading pond" />;
  if (error && !pond) return <LoadError error={error} onRetry={reload} />;

  return (
    <>
      <div>
        <Link to="/" className="back-link"><ArrowLeft size={16} aria-hidden="true" />All ponds</Link>
        <div className="page-head">
          <div>
            <h1>{pond.name}</h1>
            <p>
              Day {fmtNum(pond.days_of_culture, 0)} of culture · stocked {fmtDate(pond.stocked_at)}
              {pond.stocked_count ? ` · ${pond.stocked_count.toLocaleString()} fish` : ''}
              {pond.feeding_regime ? ` · ${pond.feeding_regime}` : ''}
            </p>
          </div>
          <div className="page-actions">
            <Link className="btn primary" to={`/sample?pond=${pond.id}`}><Camera size={18} aria-hidden="true" />New sampling round</Link>
          </div>
        </div>
      </div>

      <div className="tabs" role="tablist" aria-label="Pond modules">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            className="tab"
            onClick={() => setParams({ tab: t.id }, { replace: true })}
          >
            <t.icon size={17} aria-hidden="true" />{t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="grid fade-in" key={tab}>
        {tab === 'environment' && <EnvironmentTab pond={pond} />}
        {tab === 'health' && <HealthTab pond={pond} />}
        {tab === 'harvest' && <HarvestTab pond={pond} />}
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- Environment */

const RANGES = [
  { value: '6', label: '6 h' },
  { value: '24', label: '24 h' },
  { value: '168', label: '7 d' },
  { value: '720', label: '30 d' },
];

function BandGauge({ temp, band }) {
  const lo = band.min_c - 4;
  const hi = band.max_c + 4;
  const pct = (v) => `${Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100))}%`;
  return (
    <div>
      <div className="gauge" aria-hidden="true">
        <div className="gauge-band" style={{ left: pct(band.min_c), right: `calc(100% - ${pct(band.max_c)})` }} />
        {temp != null && <div className="gauge-marker" style={{ left: pct(temp) }} />}
      </div>
      <div className="gauge-labels"><span>{lo}°</span><span>{band.min_c}° – {band.max_c}° safe band</span><span>{hi}°</span></div>
    </div>
  );
}

function ObservationForm({ pondId, onSaved }) {
  const [algae, setAlgae] = useState(null);
  const [extra, setExtra] = useState({ do_ppm: '', ph: '', ammonia_ppm: '', nitrate_ppm: '', notes: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const toast = useToast();

  const num = (v) => (v === '' ? null : Number(v));
  const submit = async (e) => {
    e.preventDefault();
    if (algae === null) { setErr('Choose Yes or No.'); return; }
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/api/ponds/${pondId}/observations`, {
        algae_seen: algae, do_ppm: num(extra.do_ppm), ph: num(extra.ph),
        ammonia_ppm: num(extra.ammonia_ppm), nitrate_ppm: num(extra.nitrate_ppm), notes: extra.notes || null,
      });
      toast('Observation saved');
      setAlgae(null);
      setExtra({ do_ppm: '', ph: '', ammonia_ppm: '', nitrate_ppm: '', notes: '' });
      onSaved();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="stack" noValidate>
      <fieldset style={{ border: 0, padding: 0, margin: 0 }} className="stack">
        <legend className="label" style={{ fontWeight: 600, marginBottom: 8 }}>Did you see algae in the pond today?</legend>
        <div className="choice-pair">
          <button type="button" className="choice yes" aria-pressed={algae === true} onClick={() => setAlgae(true)}>
            <Leaf size={22} aria-hidden="true" />Yes, algae seen
          </button>
          <button type="button" className="choice no" aria-pressed={algae === false} onClick={() => setAlgae(false)}>
            <Droplets size={22} aria-hidden="true" />No algae
          </button>
        </div>
      </fieldset>
      <details className="disclosure">
        <summary><ChevronRight size={16} aria-hidden="true" />Add water test results (optional)</summary>
        <div className="form-grid two" style={{ marginTop: 8 }}>
          {[
            ['do_ppm', 'Dissolved oxygen', 'ppm'],
            ['ph', 'pH', ''],
            ['ammonia_ppm', 'Ammonia', 'ppm'],
            ['nitrate_ppm', 'Nitrate', 'ppm'],
          ].map(([key, label, unit]) => (
            <Field key={key} label={label} htmlFor={`obs-${key}`}>
              <div className="input-unit">
                <input id={`obs-${key}`} className="input" inputMode="decimal" type="number" step="any" min="0"
                  value={extra[key]} onChange={(e) => setExtra({ ...extra, [key]: e.target.value })} />
                {unit && <span>{unit}</span>}
              </div>
            </Field>
          ))}
        </div>
        <Field label="Notes" htmlFor="obs-notes">
          <textarea id="obs-notes" className="textarea" value={extra.notes} onChange={(e) => setExtra({ ...extra, notes: e.target.value })} />
        </Field>
      </details>
      {err && <Notice kind="error">{err}</Notice>}
      <Button type="submit" className="primary" busy={busy}>Save observation</Button>
    </form>
  );
}

function StressTiles({ stress }) {
  return (
    <div className="stats">
      <Stat label="Hours outside band" value={fmtNum(stress.hours_outside_band, 1)} unit="h" />
      <Stat label="Minimum" value={fmtNum(stress.min_c)} unit="°C" />
      <Stat label="Maximum" value={fmtNum(stress.max_c)} unit="°C" />
      <Stat label="Mean daily range" value={fmtNum(stress.mean_daily_range_c)} unit="°C" />
      <Stat label="Max rate of change" value={fmtNum(stress.max_rate_c_per_h, 2)} unit="°C/h" />
      <Stat label="Data coverage" value={fmtPct(stress.coverage)} />
    </div>
  );
}

function EnvironmentTab({ pond }) {
  const [hours, setHours] = useState('24');
  const { data, error, loading, reload } = useResource(`/api/ponds/${pond.id}/environment?hours=${hours}`, { interval: 5000 });
  const [showTable, setShowTable] = useState(false);

  if (loading && !data) return <Loading label="Loading environment" />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;
  const now = data.now;
  const obs = now.latest_observation;

  return (
    <>
      <div className="grid-main">
        <Card title="Water temperature now" icon={Thermometer}
          actions={now.source && <span className={`tag ${isSynthetic(now.source) ? 'warn' : ''}`}>{SOURCE_LABEL[now.source] || now.source}</span>}>
          <div className="row-between" style={{ alignItems: 'flex-end' }}>
            <div className="temp-hero xl">
              <span className="value">{now.stale ? '—' : fmtNum(now.temperature_c)}</span>
              <span className="unit">°C</span>
            </div>
            <EnvBadge value={now.state} size="lg" />
          </div>
          <BandGauge temp={now.stale ? null : now.temperature_c} band={now.band} />
          {now.stale && (
            <div style={{ marginTop: 12 }}>
              <Notice kind="warn">
                No reading for a while (last {fmtAgo(now.reading_ts)}{now.temperature_c != null ? `: ${fmtNum(now.temperature_c)} °C` : ''}).
                Check the probe's power and USB or network connection. The state is shown as unknown rather than assumed safe.
              </Notice>
            </div>
          )}
          <ul className="reasons" style={{ marginTop: 14 }}>
            {now.reasons.map((r) => <li key={r}>{r}</li>)}
          </ul>
          <p className="subtle" style={{ marginTop: 10 }}>Last reading {fmtDateTime(now.reading_ts)}</p>
        </Card>

        <div className="grid">
          <Card title="Season" icon={CloudSun}>
            <p style={{ fontSize: '1.25rem', fontWeight: 600 }}>{now.season}</p>
            <p className="subtle">Cool dry: Dec–Feb · Hot dry: Mar–May · Rainy: Jun–Nov</p>
          </Card>
          <Card title="Algae" icon={Leaf}>
            {obs ? (
              <div className="stack" style={{ gap: 6 }}>
                <span className={`badge ${obs.algae_seen ? 'tone-moderate' : 'tone-good'}`} style={{ justifySelf: 'start' }}>
                  {obs.algae_seen ? <Leaf size={15} aria-hidden="true" /> : <Droplets size={15} aria-hidden="true" />}
                  {obs.algae_seen ? 'Algae seen' : 'No algae'}
                </span>
                <span className="subtle">Reported {fmtAgo(obs.ts)}{obs.do_ppm != null ? ` · DO ${obs.do_ppm} ppm` : ''}</span>
              </div>
            ) : <p className="subtle">No caretaker observations yet.</p>}
          </Card>
        </div>
      </div>

      <Card
        title="Temperature trend"
        icon={History}
        hint={`Shaded area: ${now.band.min_c}–${now.band.max_c} °C safe band. Triangles mark readings outside it.`}
        actions={<div style={{ minWidth: 240 }}><Segmented name="range" label="Time range" value={hours} onChange={setHours} options={RANGES} /></div>}
      >
        <TemperatureChart points={data.history} band={now.band} hours={Number(hours)} />
        <div className="row-between" style={{ marginTop: 10 }}>
          <div className="legend">
            <span><i aria-hidden="true" />Temperature</span>
            <span><i className="band" aria-hidden="true" />Safe band</span>
            <span><i className="out" aria-hidden="true" />Outside band</span>
          </div>
          <button type="button" className="btn sm ghost" onClick={() => setShowTable((s) => !s)} aria-expanded={showTable}>
            {showTable ? 'Hide table' : 'View as table'}
          </button>
        </div>
        {showTable && (
          <div className="table-wrap" style={{ maxHeight: 280, marginTop: 10 }}>
            <table className="data">
              <thead><tr><th>Time</th><th className="num">Avg °C</th><th className="num">Min</th><th className="num">Max</th></tr></thead>
              <tbody>
                {[...data.history].reverse().map((p) => (
                  <tr key={p.ts}><td>{fmtDateTime(p.ts)}</td><td className="num">{fmtNum(p.temperature_c)}</td>
                    <td className="num">{fmtNum(p.min_c)}</td><td className="num">{fmtNum(p.max_c)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid-2">
        <Card title="Stress exposure" icon={Thermometer} hint={`Since ${data.stress_since_last_round.since}. Used to relate environment to fish condition at the next round.`}>
          <StressTiles stress={data.stress_since_last_round} />
        </Card>
        <Card title="Log a pond observation" icon={Leaf} hint="Quick check during your daily rounds.">
          <ObservationForm pondId={pond.id} onSaved={reload} />
        </Card>
      </div>

      <Card title="Observation history" icon={History} flush>
        {data.observations.length === 0 ? <Empty title="No observations yet" /> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>When</th><th>Algae</th><th className="num">DO ppm</th><th className="num">pH</th><th className="num">NH₃</th><th className="num">NO₃</th><th>Notes</th></tr></thead>
              <tbody>
                {data.observations.map((o) => (
                  <tr key={o.id}>
                    <td>{fmtDateTime(o.ts)}</td>
                    <td>{o.algae_seen ? <span className="tag warn">Yes</span> : <span className="tag">No</span>}</td>
                    <td className="num">{fmtNum(o.do_ppm)}</td><td className="num">{fmtNum(o.ph)}</td>
                    <td className="num">{fmtNum(o.ammonia_ppm, 2)}</td><td className="num">{fmtNum(o.nitrate_ppm, 2)}</td>
                    <td style={{ whiteSpace: 'normal', minWidth: 160 }}>{o.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

/* ---------------------------------------------------------------- Fish health */

function HealthTab({ pond }) {
  const { data: rounds, error, loading, reload } = useResource(`/api/ponds/${pond.id}/rounds`);
  if (loading && !rounds) return <Loading label="Loading rounds" />;
  if (error && !rounds) return <LoadError error={error} onRetry={reload} />;
  const latest = pond.latest_round;

  return (
    <>
      {latest && (
        <Card title="Latest health status" icon={Fish}
          hint={`Round on ${fmtDate(latest.sampled_at)} · day ${fmtNum(latest.days_of_culture, 0)}`}
          actions={<Link to={`/rounds/${latest.id}`} className="btn sm">Open round</Link>}>
          <div className="row" style={{ marginBottom: 12 }}>
            <HealthBadge value={latest.health.status} size="lg" />
            {latest.health.share_flagged != null && (
              <span className="subtle">{latest.health.n_flagged} of {latest.health.n_scored} fish flagged ({fmtPct(latest.health.share_flagged)})</span>
            )}
          </div>
          <ul className="reasons">{latest.health.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="subtle" style={{ marginTop: 10 }}>Screening of visible indicators only. Flagged fish should be set aside for a technician; the system does not diagnose disease.</p>
        </Card>
      )}

      <Card title="Sampling rounds" icon={History} flush
        actions={<Link className="btn sm primary" to={`/sample?pond=${pond.id}`}><Camera size={16} aria-hidden="true" />New round</Link>}>
        {rounds.length === 0 ? (
          <Empty icon={Camera} title="No sampling rounds yet">Photograph and weigh a sample of fish to assess health and readiness.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr><th>Date</th><th className="num">Day</th><th>Capture</th><th className="num">Fish</th><th className="num">Mean g</th><th className="num">Mean FCI</th><th>Health</th><th>Readiness</th><th>Status</th></tr>
              </thead>
              <tbody>
                {rounds.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/rounds/${r.id}`}>{fmtDay(r.sampled_at)}</Link></td>
                    <td className="num">{fmtNum(r.days_of_culture, 0)}</td>
                    <td>{r.capture_condition || '—'}</td>
                    <td className="num">{r.n_fish}</td>
                    <td className="num">{fmtNum(r.mean_weight_g, 0)}</td>
                    <td className="num">{fmtNum(r.mean_fci, 2)}</td>
                    <td><HealthBadge value={r.health_status} /></td>
                    <td><ReadinessBadge value={r.readiness_status} /></td>
                    <td>{r.status === 'completed' ? <span className="tag">Recorded</span> : <span className="tag warn">Draft</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

/* ---------------------------------------------------------------- Harvest */

function HarvestTab({ pond }) {
  const { data, error, loading, reload } = useResource(`/api/ponds/${pond.id}/growth`);
  if (loading && !data) return <Loading label="Loading growth" />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;
  const latest = pond.latest_round;
  const trend = data.trend;

  return (
    <>
      {latest ? (
        <Card title="Harvest readiness" icon={Waves}
          hint={`At the round on ${fmtDate(latest.sampled_at)} (day ${fmtNum(latest.days_of_culture, 0)}).`}>
          <div className="row" style={{ marginBottom: 8 }}>
            <ReadinessBadge value={latest.readiness} size="lg" />
            <span className="subtle">{latest.readiness_detail.size.n} fish sampled</span>
          </div>
          <Checklist criteria={latest.readiness_detail.criteria} />
          <ul className="reasons" style={{ marginTop: 10 }}>
            {latest.readiness_detail.notes.map((n) => <li key={n}>{n}</li>)}
          </ul>
        </Card>
      ) : (
        <Card><Empty icon={Waves} title="No sampling rounds yet">Readiness is assessed from weighed and measured fish at each round.</Empty></Card>
      )}

      <Card title="Growth over the culture period" icon={Fish}
        hint={trend.method === 'polynomial'
          ? `Degree-2 polynomial of mean weight on days of culture (R² ${fmtNum(trend.poly.r2, 3)}), drawn only over the observed days.`
          : `Specific growth rate between rounds. A growth curve is fitted once ${'at least five'} rounds exist (${trend.n_rounds} so far).`}>
        <GrowthChart rounds={data.rounds} poly={trend.poly} target={data.target_weight_g} />
        <div className="legend" style={{ marginTop: 10 }}>
          <span><i aria-hidden="true" />Mean weight per round</span>
          {trend.poly && <span><i className="dot" aria-hidden="true" />Fitted trend (not a forecast)</span>}
          <span><i className="dash" aria-hidden="true" />Target market size</span>
        </div>
      </Card>

      <Card title="Size by round" icon={History} flush>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Date</th><th className="num">Day</th><th className="num">Fish</th><th className="num">Mean g</th><th className="num">At target</th><th className="num">CV</th><th className="num">Mean K</th><th className="num">SGR %/day</th></tr></thead>
            <tbody>
              {data.rounds.map((r, i) => {
                const sgr = i > 0 ? trend.sgr_by_interval[i - 1]?.sgr : null;
                return (
                  <tr key={r.id}>
                    <td><Link to={`/rounds/${r.id}`}>{fmtDay(r.sampled_at)}</Link></td>
                    <td className="num">{fmtNum(r.doc, 0)}</td>
                    <td className="num">{r.n}</td>
                    <td className="num">{fmtNum(r.mean_weight_g, 0)}</td>
                    <td className="num">{fmtPct(r.share_at_target)}</td>
                    <td className="num">{fmtNum(r.weight_cv, 2)}</td>
                    <td className="num">{fmtNum(r.mean_k, 2)}</td>
                    <td className="num">{fmtNum(sgr, 2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
