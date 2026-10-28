import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Camera, CheckCircle2, CircleSlash, ClipboardCheck, Fish, Flag, ImageOff, Lock,
  MinusCircle, Thermometer, Trash2, Waves, XCircle,
} from 'lucide-react';
import { api, useResource } from '../lib/api';
import { fmtDate, fmtNum, fmtPct, fmtTime } from '../lib/format';
import { Button, Card, Empty, Field, LoadError, Loading, Notice, Stat, useToast } from '../components/ui';
import { HealthBadge, ReadinessBadge } from '../components/Status';

export function Checklist({ criteria }) {
  return (
    <ul className="checklist">
      {criteria.map((c) => (
        <li key={c.key}>
          {c.passed === true && <CheckCircle2 size={20} className="ok" aria-label="met" />}
          {c.passed === false && <XCircle size={20} className="no" aria-label="not met" />}
          {c.passed == null && <MinusCircle size={20} className="na" aria-label="descriptive" />}
          <span>{c.label}</span>
          <span className="val">{c.value}<small>{c.target}</small></span>
        </li>
      ))}
    </ul>
  );
}

function QcIcons({ quality }) {
  if (!quality) return <span className="subtle">—</span>;
  const failed = quality.checks.filter((c) => !c.passed);
  if (!failed.length) return <span className="badge tone-good"><CheckCircle2 size={14} aria-hidden="true" />Pass</span>;
  return (
    <span className="badge tone-moderate" title={failed.map((c) => c.label).join(', ')}>
      <CircleSlash size={14} aria-hidden="true" />{failed.map((c) => c.label).join(', ')}
    </span>
  );
}

function TechnicianAssessment({ round, onSaved }) {
  const [health, setHealth] = useState(round.technician_health || '');
  const [ready, setReady] = useState(round.technician_readiness || '');
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.patch(`/api/rounds/${round.id}`, { technician_health: health || null, technician_readiness: ready || null });
      toast('Technician assessment saved');
      onSaved();
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={save} className="stack">
      <div className="form-grid two">
        <Field label="Health (technician)" htmlFor="tech-h">
          <select id="tech-h" className="select" value={health} onChange={(e) => setHealth(e.target.value)}>
            <option value="">Not assessed</option>
            <option>Normal</option><option>Watch</option><option>Refer to technician</option>
          </select>
        </Field>
        <Field label="Harvest readiness (technician)" htmlFor="tech-r">
          <select id="tech-r" className="select" value={ready} onChange={(e) => setReady(e.target.value)}>
            <option value="">Not assessed</option>
            <option>Not Ready</option><option>Approaching</option><option>Ready</option>
          </select>
        </Field>
      </div>
      <Button type="submit" busy={busy} className="sm" style={{ justifySelf: 'start' }}>Save assessment</Button>
    </form>
  );
}

export default function RoundDetail() {
  const { roundId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data: r, error, loading, reload } = useResource(`/api/rounds/${roundId}`);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  if (loading && !r) return <Loading label="Loading round" />;
  if (error && !r) return <LoadError error={error} onRetry={reload} />;

  const a = r.assessment;
  const draft = r.status !== 'completed';
  const stubbed = r.fish.some((f) => f.detection?.is_stub);
  const seeded = r.fish.some((f) => f.analysis_source === 'seed');

  const complete = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/api/rounds/${r.id}/complete`);
      toast('Round recorded');
      reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!window.confirm('Delete this draft round and its fish?')) return;
    await api.del(`/api/rounds/${r.id}`);
    navigate(`/ponds/${r.pond_id}?tab=health`);
  };

  return (
    <>
      <div>
        <Link to={`/ponds/${r.pond_id}?tab=health`} className="back-link"><ArrowLeft size={16} aria-hidden="true" />{r.pond.name}</Link>
        <div className="page-head">
          <div>
            <div className="eyebrow">
              {draft ? <span className="tag warn">Draft: assessment updates live</span> : <span className="tag"><Lock size={12} aria-hidden="true" />Recorded</span>}
            </div>
            <h1>Sampling round · {fmtDate(r.sampled_at)}</h1>
            <p>
              Day {fmtNum(r.days_of_culture, 0)} · {fmtTime(r.sampled_at)} ({r.time_of_day})
              {r.capture_condition ? ` · ${r.capture_condition}` : ''}{r.weather ? ` · ${r.weather}` : ''}
              {r.phone_model ? ` · ${r.phone_model}` : ''}
            </p>
          </div>
          {draft && (
            <div className="page-actions">
              <Button icon={Trash2} className="danger" onClick={remove}>Delete draft</Button>
              <Link className="btn" to={`/sample/${r.id}`}><Camera size={18} aria-hidden="true" />Add fish</Link>
              <Button icon={ClipboardCheck} className="primary" busy={busy} onClick={complete} disabled={!r.fish.length}>Complete round</Button>
            </div>
          )}
        </div>
      </div>

      {err && <Notice kind="error">{err}</Notice>}
      {(stubbed || seeded) && (
        <Notice kind="warn">
          {seeded ? 'This round uses seeded demo fish. ' : ''}
          {stubbed ? 'Image indicators come from the placeholder detector (no trained YOLO26 weights yet), so FCI values are for testing the workflow only.' : ''}
        </Notice>
      )}

      <div className="grid-2">
        <Card title="Fish health" icon={Fish}>
          <div className="row" style={{ marginBottom: 10 }}>
            <HealthBadge value={a.health.status} size="lg" />
            {a.health.share_flagged != null && <span className="subtle">{a.health.n_flagged} of {a.health.n_scored} flagged</span>}
          </div>
          <ul className="reasons">{a.health.reasons.map((x) => <li key={x}>{x}</li>)}</ul>
        </Card>
        <Card title="Harvest readiness" icon={Waves}>
          <div className="row" style={{ marginBottom: 6 }}>
            <ReadinessBadge value={a.readiness.status} size="lg" />
          </div>
          {a.readiness.criteria.length ? <Checklist criteria={a.readiness.criteria} /> : <p className="subtle">Add weighed fish to assess readiness.</p>}
          <ul className="reasons" style={{ marginTop: 10 }}>{a.readiness.notes.map((x) => <li key={x}>{x}</li>)}</ul>
        </Card>
      </div>

      <Card title="Environment before this round" icon={Thermometer}
        hint={`Stress exposure from the previous round to this one · ${a.stress.season} season · ${a.stress.algae_reports} algae report(s)`}>
        <div className="stats">
          <Stat label="Hours outside band" value={fmtNum(a.stress.hours_outside_band, 1)} unit="h" />
          <Stat label="Minimum" value={fmtNum(a.stress.min_c)} unit="°C" />
          <Stat label="Maximum" value={fmtNum(a.stress.max_c)} unit="°C" />
          <Stat label="Mean daily range" value={fmtNum(a.stress.mean_daily_range_c)} unit="°C" />
          <Stat label="Max rate" value={fmtNum(a.stress.max_rate_c_per_h, 2)} unit="°C/h" />
          <Stat label="Coverage" value={fmtPct(a.stress.coverage)} />
          <Stat label="Critical reached" value={a.env_critical_in_interval ? 'Yes' : 'No'} />
        </div>
      </Card>

      <Card title={`Sampled fish (${r.fish.length})`} icon={Fish} flush
        hint="K = 100·W/L³. FCI estimates the technician's 1–5 condition score; fish below the threshold are flagged.">
        {r.fish.length === 0 ? (
          <Empty icon={Camera} title="No fish recorded yet" action={draft && <Link className="btn primary" to={`/sample/${r.id}`}>Add fish</Link>} />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr><th>#</th><th>Photo</th><th className="num">Weight g</th><th className="num">Length cm</th><th className="num">Image cm</th><th className="num">K</th>
                  <th className="num">Gill</th><th className="num">Skin</th><th className="num">Fin</th><th className="num">Eye</th>
                  <th className="num">FCI</th><th>Flag</th><th>Image check</th><th className="num">Tech score</th></tr>
              </thead>
              <tbody>
                {r.fish.map((f) => (
                  <tr key={f.id} className={f.flagged ? 'flagged' : ''}>
                    <td className="num">{f.seq}</td>
                    <td>
                      {f.photo_url
                        ? <a href={f.photo_url} target="_blank" rel="noreferrer"><img className="thumb" src={f.photo_url} alt={`Fish ${f.seq}`} loading="lazy" /></a>
                        : <span className="thumb-ph" title={f.analysis_source === 'seed' ? 'Demo fish' : 'No photo'}><ImageOff size={16} aria-hidden="true" /></span>}
                    </td>
                    <td className="num">{fmtNum(f.weight_g, 1)}</td>
                    <td className="num">{fmtNum(f.length_cm, 1)}</td>
                    <td className="num">{fmtNum(f.image_length_cm, 1)}</td>
                    <td className="num">{fmtNum(f.condition_factor, 2)}</td>
                    <td className="num">{fmtNum(f.gill_color_index, 2)}</td>
                    <td className="num">{fmtNum(f.skin_color_index, 2)}</td>
                    <td className="num">{fmtNum(f.fin_integrity, 2)}</td>
                    <td className="num">{fmtNum(f.eye_clarity, 2)}</td>
                    <td className="num"><strong>{fmtNum(f.fci, 2)}</strong></td>
                    <td>{f.flagged ? <span className="badge tone-critical"><Flag size={13} aria-hidden="true" />Set aside</span> : <span className="subtle">—</span>}</td>
                    <td><QcIcons quality={f.quality} /></td>
                    <td className="num">{fmtNum(f.technician_score, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Technician's independent assessment" icon={ClipboardCheck}
        hint="Recorded separately from the system's status. Used to measure agreement on the Evaluation page.">
        <TechnicianAssessment round={r} onSaved={reload} />
      </Card>
    </>
  );
}
