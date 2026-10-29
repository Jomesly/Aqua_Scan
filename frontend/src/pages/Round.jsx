import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Camera, CheckCheck, ChevronLeft, ImageOff, Loader2, Plus, RotateCcw, Ruler, Scale, Trash2, TriangleAlert,
} from 'lucide-react';
import { Button, Card, LoadError, Loading, Notice, useToast } from '../components/ui';
import { ClassBadge, DemoTag, HealthBadge } from '../components/Status';
import { RoundAssessment } from '../components/Assessment';
import { api, useResource } from '../lib/api';
import { can, useAuth } from '../lib/auth';
import { fmtDate, fmtNum, SIGNS_LABEL } from '../lib/format';

function PhotoSlot({ fish, side, onDone, disabled }) {
  const photo = fish.photos.find((p) => p.side === side);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const id = `ph-${fish.id}-${side}`;

  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy(true);
    setErr(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      onDone(await api.form(`/api/fish/${fish.id}/photos/${side}`, fd));
    } catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  };

  return (
    <div className={`photo-slot ${photo ? (photo.ok ? 'ok' : 'bad') : ''}`}>
      <label htmlFor={id} className="photo-drop">
        <input id={id} type="file" accept="image/*" capture="environment" onChange={upload} disabled={busy || disabled} />
        {photo ? (
          <img src={photo.annotated_url || photo.url} alt={`Fish ${fish.code} side ${side}`} loading="lazy" />
        ) : (
          <span className="ph-inner"><Camera size={26} aria-hidden="true" /><span>Side {side}</span><small>Tap to take photo</small></span>
        )}
        {busy && <span className="photo-busy"><Loader2 size={22} className="spin" aria-hidden="true" />Checking and screening…</span>}
      </label>
      {photo && (
        <div className="photo-meta">
          <span className="xs"><strong>Side {side}</strong>{photo.length_cm != null && ` · L ${fmtNum(photo.length_cm)} cm`}
            {photo.top && ` · ${photo.top.cls} ${Math.round(photo.top.conf * 100)}%`}</span>
          {!disabled && (
            <label htmlFor={id} className="btn sm ghost"><RotateCcw size={14} aria-hidden="true" />Retake</label>
          )}
        </div>
      )}
      {photo && !photo.ok && (
        <div className="photo-fail" role="alert">
          <TriangleAlert size={16} aria-hidden="true" />
          <div><strong>Retake needed.</strong>{photo.reasons.map((r) => <div key={r}>{r}</div>)}</div>
        </div>
      )}
      {photo?.ok && photo.reasons.length > 0 && <p className="xs muted">{photo.reasons.join(' ')}</p>}
      {err && <p className="xs tone-critical">{err}</p>}
    </div>
  );
}

function Measure({ fish }) {
  const noScale = fish.photos.length > 0 && fish.length_cm == null;
  return (
    <dl className="measure">
      <div><dt>Length</dt><dd>{fish.length_cm != null ? `${fmtNum(fish.length_cm)} cm` : noScale ? 'No scale' : '—'}</dd></div>
      <div><dt>Area</dt><dd>{fish.area_cm2 != null ? `${fmtNum(fish.area_cm2, 0)} cm²` : '—'}</dd></div>
      <div><dt>Est. weight</dt><dd>{fish.est_weight_g != null ? `${fmtNum(fish.est_weight_g, 0)} g` : '—'}</dd></div>
      <div><dt>K</dt><dd>{fmtNum(fish.k, 2)}</dd></div>
    </dl>
  );
}

function FishCapture({ fish, onChange, onDelete, boardMode }) {
  const [vals, setVals] = useState({ scale_weight_g: fish.scale_weight_g ?? '', ruler_length_cm: fish.ruler_length_cm ?? '' });
  const save = async (k) => {
    const v = vals[k] === '' ? null : Number(vals[k]);
    if (v === (fish[k] ?? null)) return;
    try { onChange(await api.patch(`/api/fish/${fish.id}`, { [k]: v })); } catch { /* shown on next load */ }
  };
  return (
    <Card className="fish-card" title={`Fish ${fish.code}`}
      actions={<button type="button" className="btn sm ghost icon" aria-label={`Remove fish ${fish.code}`} onClick={onDelete}><Trash2 size={16} /></button>}>
      <div className="photo-pair">
        <PhotoSlot fish={fish} side="A" onDone={(r) => onChange(r.fish)} />
        <PhotoSlot fish={fish} side="B" onDone={(r) => onChange(r.fish)} />
      </div>
      <div className="form-grid two compact">
        <label className="field">
          <span className="label-text"><Scale size={14} aria-hidden="true" /> Scale weight (g)</span>
          <input className="input" type="number" inputMode="decimal" min="0" step="0.1" value={vals.scale_weight_g}
            onChange={(e) => setVals({ ...vals, scale_weight_g: e.target.value })} onBlur={() => save('scale_weight_g')} />
        </label>
        <label className="field">
          <span className="label-text"><Ruler size={14} aria-hidden="true" /> Ruler total length (cm)</span>
          <input className="input" type="number" inputMode="decimal" min="0" step="0.1" value={vals.ruler_length_cm}
            onChange={(e) => setVals({ ...vals, ruler_length_cm: e.target.value })} onBlur={() => save('ruler_length_cm')} />
        </label>
      </div>
      {fish.photos.some((p) => p.ok) && (
        <div className="fish-result">
          <div className="row wrap gap-s">{fish.cls && <ClassBadge cls={fish.cls} conf={fish.conf} />}<HealthBadge value={fish.status} />
            <span className={`tag ${fish.sides === 2 ? 'good' : 'warn'}`}>{fish.sides} of 2 photos</span></div>
          {boardMode && <Measure fish={fish} />}
          <ul className="reasons">{fish.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        </div>
      )}
    </Card>
  );
}

function Capture({ round, reload, setRound }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState(null);
  const replaceFish = (f) => setRound({ ...round, fish: round.fish.map((x) => (x.id === f.id ? f : x)) });

  const addFish = async () => {
    setBusy('add');
    try {
      const f = await api.post(`/api/rounds/${round.id}/fish`, {});
      setRound({ ...round, fish: [...round.fish, f] });
      setTimeout(() => document.getElementById(`ph-${f.id}-A`)?.closest('.fish-card')?.scrollIntoView({ behavior: 'smooth' }), 50);
    } finally { setBusy(null); }
  };
  const removeFish = async (f) => {
    if (!window.confirm(`Remove fish ${f.code} and its photos?`)) return;
    await api.del(`/api/fish/${f.id}`);
    reload();
  };
  const complete = async () => {
    const missing = round.fish.filter((f) => !f.photos.some((p) => p.ok)).length;
    const msg = missing
      ? `${missing} fish have no accepted photo and will count as not screened. Complete the round anyway?`
      : 'Complete this round? The statuses will be saved and the round can no longer be edited.';
    if (!window.confirm(msg)) return;
    setBusy('done');
    try {
      await api.post(`/api/rounds/${round.id}/complete`);
      toast('Round completed and saved');
      await reload();
    } finally { setBusy(null); }
  };
  const discard = async () => {
    if (!window.confirm('Delete this draft round and all its photos?')) return;
    await api.del(`/api/rounds/${round.id}`);
    navigate(`/ponds/${round.pond_id}`);
  };
  const okCount = round.fish.filter((f) => f.photos.some((p) => p.ok)).length;

  return (
    <div className="stack">
      <div className="steps" aria-label="Progress">
        <span className="step on"><b>1</b>Round details</span><span className="sep" />
        <span className="step on"><b>2</b>Photograph and weigh</span><span className="sep" />
        <span className="step"><b>3</b>Complete</span>
      </div>
      {round.board_mode ? (
        <Notice kind="info">
          For each fish: photograph <strong>Side A</strong> and <strong>Side B</strong> on the board, then enter the scale weight and the
          ruler length. A photo that fails the check shows why. Retake it while the fish is still on the board.
        </Notice>
      ) : (
        <Notice kind="info">
          For each fish: upload a photo of <strong>Side A</strong> and, if you have one, <strong>Side B</strong>. Each photo is screened for
          signs of Aeromonas and TiLV. Without the board, length and weight are not measured.
        </Notice>
      )}
      {round.fish.length === 0 && <p className="muted">No fish yet. Add the first sampled fish.</p>}
      <div className="fish-list">
        {round.fish.map((f) => (
          <FishCapture key={f.id} fish={f} boardMode={round.board_mode} onChange={replaceFish} onDelete={() => removeFish(f)} />
        ))}
      </div>
      <details className="disclosure card">
        <summary>Live preview of the round statuses</summary>
        <div style={{ marginTop: 12 }}><RoundAssessment a={round.assessment} live /></div>
      </details>
      <div className="sticky-actions">
        <Button className="primary" icon={Plus} busy={busy === 'add'} onClick={addFish}>Add fish</Button>
        <Button icon={CheckCheck} busy={busy === 'done'} onClick={complete} disabled={!round.fish.length}>
          Complete round ({okCount}/{round.fish.length})
        </Button>
        <button type="button" className="btn ghost danger" onClick={discard}>Discard</button>
      </div>
    </div>
  );
}

function TechAssessment({ round, onSaved }) {
  const [v, setV] = useState({ tech_health: round.tech_health || '', tech_readiness: round.tech_readiness || '' });
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const save = async () => {
    setBusy(true);
    try {
      await api.post(`/api/rounds/${round.id}/assessment`, v);
      toast('Technician assessment saved');
      onSaved();
    } finally { setBusy(false); }
  };
  return (
    <Card title="Technician's independent assessment" hint="Recorded without looking at the system's status. Used for the agreement evaluation.">
      <div className="form-grid two">
        <label className="field"><span className="label-text">Pond health</span>
          <select className="select" value={v.tech_health} onChange={(e) => setV({ ...v, tech_health: e.target.value })}>
            <option value="">Not assessed</option>
            {['Normal', 'Watch', 'Refer to technician'].map((x) => <option key={x}>{x}</option>)}
          </select></label>
        <label className="field"><span className="label-text">Harvest readiness</span>
          <select className="select" value={v.tech_readiness} onChange={(e) => setV({ ...v, tech_readiness: e.target.value })}>
            <option value="">Not assessed</option>
            {['Not Ready', 'Approaching', 'Ready'].map((x) => <option key={x}>{x}</option>)}
          </select></label>
      </div>
      <Button className="primary" busy={busy} onClick={save} style={{ marginTop: 12 }}>Save assessment</Button>
    </Card>
  );
}

function TechSigns({ fish, onSaved }) {
  const [busy, setBusy] = useState(false);
  const save = async (signs) => {
    if (!signs) return;
    setBusy(true);
    try { await api.post(`/api/fish/${fish.id}/review`, { signs, note: fish.tech_note }); onSaved(); } finally { setBusy(false); }
  };
  return (
    <select className="select sm" aria-label={`Technician check of fish ${fish.code}`} disabled={busy}
      value={fish.tech_signs || ''} onChange={(e) => save(e.target.value)}>
      <option value="">Not checked</option>
      {Object.entries(SIGNS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
    </select>
  );
}

function Results({ round, reload, user }) {
  return (
    <div className="stack">
      <RoundAssessment a={round.assessment} />
      {can.review(user) && <TechAssessment round={round} onSaved={reload} />}
      <Card title="Sampled fish" flush hint={can.review(user)
        ? 'Screening shows visible signs only. It is not a diagnosis. Record your check of any fish, not only the flagged ones, so the evaluation also counts the fish the system called Normal.'
        : 'Screening shows visible signs only. It is not a diagnosis.'}>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr><th>Fish</th><th>Photos</th><th>Screening</th><th>Status</th><th className="num">L cm</th>
                <th className="num">Est. g</th><th className="num">Scale g</th><th className="num">Ruler cm</th><th className="num">K</th><th>Technician</th></tr>
            </thead>
            <tbody>
              {round.fish.map((f) => (
                <tr key={f.id} className={f.status === 'Refer to technician' ? 'flagged' : ''}>
                  <td><strong>{f.code}</strong>{f.source === 'demo' && <DemoTag />}</td>
                  <td>
                    <div className="row gap-s">
                      {f.photos.length ? f.photos.map((p) => (
                        <a key={p.id} href={p.annotated_url || p.url} target="_blank" rel="noreferrer" aria-label={`Open side ${p.side} photo`}>
                          <img className="thumb" src={p.annotated_url || p.url} alt="" loading="lazy" />
                        </a>
                      )) : <span className="thumb-ph" title="No photos (demo data)"><ImageOff size={16} aria-hidden="true" /></span>}
                    </div>
                    {f.photos.length > 0 && <span className="xs subtle">{f.sides} of 2 photos</span>}
                  </td>
                  <td>{f.cls ? <ClassBadge cls={f.cls} conf={f.conf} /> : <span className="subtle">—</span>}</td>
                  <td><HealthBadge value={f.status} /></td>
                  <td className="num">{fmtNum(f.length_cm)}</td>
                  <td className="num">{fmtNum(f.est_weight_g, 0)}</td>
                  <td className="num">{fmtNum(f.scale_weight_g, 0)}</td>
                  <td className="num">{fmtNum(f.ruler_length_cm)}</td>
                  <td className="num">{fmtNum(f.k, 2)}</td>
                  <td className="small">
                    {can.review(user)
                      ? <TechSigns fish={f} onSaved={reload} />
                      : f.tech_signs ? SIGNS_LABEL[f.tech_signs] : <span className="subtle">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

export default function Round() {
  const { roundId } = useParams();
  const { user } = useAuth();
  const { data, error, loading, reload } = useResource(`/api/rounds/${roundId}`, { deps: [roundId] });
  const [local, setLocal] = useState(null);
  if (loading && !data) return <Loading />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;
  const round = local && local.id === data.id && local.status === data.status ? local : data;
  const doReload = async () => { setLocal(null); await reload(); };
  const setRound = (r) => setLocal(r);
  const editing = round.status === 'draft' && can.sample(user);

  return (
    <div className="stack">
      <Link to={`/ponds/${round.pond_id}`} className="back-link"><ChevronLeft size={18} aria-hidden="true" />{round.pond_name}</Link>
      <div className="page-head">
        <span className="eyebrow">
          Sampling round · {round.status === 'draft' ? 'Draft' : 'Completed'}
          {round.source === 'demo' && <DemoTag />}
          {!round.board_mode && <span className="tag">No board: screening only</span>}
        </span>
        <h1>{round.pond_name}, {fmtDate(round.sampled_at)}</h1>
        <p>Day {fmtNum(round.days_of_culture, 0)} of culture · {round.fish.length} fish
          {round.capture_condition ? ` · ${round.capture_condition}` : ''}{round.created_by ? ` · by ${round.created_by}` : ''}</p>
      </div>
      {editing
        ? <Capture round={round} reload={doReload} setRound={(r) => { setRound(r); api.get(`/api/rounds/${round.id}`).then(setLocal); }} />
        : <Results round={round} reload={doReload} user={user} />}
    </div>
  );
}
