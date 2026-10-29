import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, ClipboardList, ImageOff, Stethoscope } from 'lucide-react';
import { Button, Card, Empty, LoadError, Loading, Notice, useToast } from '../components/ui';
import { ClassBadge, DemoTag, HealthBadge, ReadinessBadge } from '../components/Status';
import { api, useResource } from '../lib/api';
import { fmtDate, fmtNum, SIGNS_LABEL } from '../lib/format';

function FishReview({ fish, onDone }) {
  const [signs, setSigns] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/api/fish/${fish.id}/review`, { signs, note: note || null });
      toast(`Check recorded for fish ${fish.code}`);
      onDone();
    } finally { setBusy(false); }
  };
  return (
    <Card className={`review-card ${fish.status === 'Refer to technician' ? 'crit' : 'attn'}`}
      title={`${fish.pond_name} · fish ${fish.code}`} hint={`Round of ${fmtDate(fish.sampled_at)}`}
      actions={fish.source === 'demo' ? <DemoTag /> : null}>
      <div className="review-grid">
        <div className="review-photos">
          {fish.photos.length ? fish.photos.map((p) => (
            <a key={p.id} href={p.annotated_url || p.url} target="_blank" rel="noreferrer">
              <img src={p.annotated_url || p.url} alt={`Fish ${fish.code}, side ${p.side}`} loading="lazy" />
            </a>
          )) : <div className="thumb-ph lg"><ImageOff size={24} aria-hidden="true" /><span className="xs">No photo (demo data)</span></div>}
        </div>
        <div className="stack">
          <div className="row wrap gap-s"><ClassBadge cls={fish.cls} conf={fish.conf} /><HealthBadge value={fish.status} /></div>
          <ul className="reasons">{fish.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="small muted">L {fmtNum(fish.length_cm)} cm · est. {fmtNum(fish.est_weight_g, 0)} g · K {fmtNum(fish.k, 2)}</p>
          <fieldset className="radio-list">
            <legend className="label-text">Your check of the visible defect</legend>
            {Object.entries(SIGNS_LABEL).map(([k, label]) => (
              <label key={k}><input type="radio" name={`signs-${fish.id}`} value={k} checked={signs === k} onChange={() => setSigns(k)} />{label}</label>
            ))}
          </fieldset>
          <label className="field"><span className="label-text">Note (optional), e.g. lab test sent</span>
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></label>
          <Button className="primary" icon={CheckCircle2} busy={busy} disabled={!signs} onClick={save}>Record check</Button>
        </div>
      </div>
    </Card>
  );
}

export default function Review() {
  const { data, error, loading, reload } = useResource('/api/review/queue');
  if (loading && !data) return <Loading />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;
  return (
    <div className="stack">
      <div className="page-head">
        <span className="eyebrow">Technician</span>
        <h1>Review queue</h1>
        <p>Fish marked Watch or Refer to technician, and completed rounds that still need your independent pond assessment.</p>
      </div>
      <Notice kind="info">Record what you see <strong>before</strong> reading the system's result where possible. Your checks are the
        reference for the screening and status evaluation.</Notice>

      <h2 className="section-title"><Stethoscope size={18} aria-hidden="true" /> Flagged fish ({data.fish.length})</h2>
      {data.fish.length === 0
        ? <Empty icon={CheckCircle2} title="No flagged fish waiting">Every flagged fish has been checked.</Empty>
        : data.fish.map((f) => <FishReview key={f.id} fish={f} onDone={reload} />)}

      <h2 className="section-title"><ClipboardList size={18} aria-hidden="true" /> Rounds needing a pond assessment ({data.rounds.length})</h2>
      {data.rounds.length === 0 ? <p className="muted">None.</p> : (
        <Card flush>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Pond</th><th>Date</th><th>System health</th><th>System readiness</th><th /></tr></thead>
              <tbody>
                {data.rounds.map((r) => (
                  <tr key={r.id}>
                    <td>{r.pond_name}{r.source === 'demo' && <DemoTag />}</td>
                    <td>{fmtDate(r.sampled_at)}</td>
                    <td><HealthBadge value={r.health} /></td>
                    <td><ReadinessBadge value={r.readiness} /></td>
                    <td><Link className="btn sm" to={`/rounds/${r.id}`}>Assess</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
