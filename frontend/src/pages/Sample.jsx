import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, Camera, CheckCircle2, ChevronRight, Cloud, CloudRain, ClipboardCheck, Fish, Flag,
  ImagePlus, Plus, Sun, TreePine, XCircle,
} from 'lucide-react';
import { api, useResource } from '../lib/api';
import { fmtDay, fmtNum } from '../lib/format';
import { Button, Card, Empty, Field, LoadError, Loading, Notice, Segmented, useToast } from '../components/ui';

const CAPTURE = [
  { value: 'open sunlight', label: 'Sunlight', icon: Sun },
  { value: 'shade', label: 'Shade', icon: TreePine },
  { value: 'overcast', label: 'Overcast', icon: Cloud },
];
const WEATHER = [
  { value: 'Sunny', label: 'Sunny' },
  { value: 'Cloudy', label: 'Cloudy' },
  { value: 'Light rain', label: 'Light rain' },
  { value: 'Rain', label: 'Rain' },
];

function Steps({ step }) {
  return (
    <div className="steps" aria-label={`Step ${step} of 2`}>
      <span className={`step ${step >= 1 ? 'on' : ''}`}><b>1</b>Round details</span>
      <span className="sep" aria-hidden="true" />
      <span className={`step ${step >= 2 ? 'on' : ''}`}><b>2</b>Photograph &amp; weigh fish</span>
    </div>
  );
}

export function SampleStart() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { data: ponds, error, loading, reload } = useResource('/api/ponds');
  const [pondId, setPondId] = useState(params.get('pond') || '');
  const [capture, setCapture] = useState('shade');
  const [weather, setWeather] = useState('Sunny');
  const [phone, setPhone] = useState(() => localStorage.getItem('phone_model') || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!pondId && ponds?.length === 1) setPondId(String(ponds[0].id));
  }, [ponds, pondId]);

  if (loading && !ponds) return <Loading label="Loading ponds" />;
  if (error && !ponds) return <LoadError error={error} onRetry={reload} />;

  const drafts = ponds.filter((p) => p.latest_round?.status === 'draft');

  const start = async (e) => {
    e.preventDefault();
    if (!pondId) { setErr('Choose the pond you are sampling.'); return; }
    setBusy(true);
    setErr(null);
    try {
      localStorage.setItem('phone_model', phone);
      const r = await api.post(`/api/ponds/${pondId}/rounds`, {
        capture_condition: capture, weather, phone_model: phone || null,
      });
      navigate(`/sample/${r.id}`);
    } catch (ex) {
      setErr(ex.message);
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <Steps step={1} />
          <h1 style={{ marginTop: 10 }}>New sampling round</h1>
          <p>Place each sampled fish on the board with the printed scale and color card, photograph it, then weigh and measure it.</p>
        </div>
      </div>

      {drafts.length > 0 && (
        <Notice kind="info">
          Unfinished round{drafts.length > 1 ? 's' : ''}:{' '}
          {drafts.map((p, i) => (
            <span key={p.id}>{i > 0 && ', '}<Link to={`/sample/${p.latest_round.id}`}>{p.name} ({fmtDay(p.latest_round.sampled_at)})</Link></span>
          ))}. Continue instead of starting a new one.
        </Notice>
      )}

      {ponds.length === 0 ? (
        <Card><Empty icon={Fish} title="No ponds yet" action={<Link className="btn primary" to="/settings#ponds">Add a pond</Link>} /></Card>
      ) : (
        <form onSubmit={start} className="grid" noValidate>
          <Card title="Which pond?">
            <div className="pond-pick" role="radiogroup" aria-label="Pond">
              {ponds.map((p) => (
                <label key={p.id}>
                  <input type="radio" name="pond" value={p.id} checked={String(pondId) === String(p.id)} onChange={() => setPondId(String(p.id))} />
                  <strong>{p.name}</strong>
                  <span className="subtle">Day {fmtNum(p.days_of_culture, 0)} · {p.rounds_count} round{p.rounds_count === 1 ? '' : 's'}</span>
                </label>
              ))}
            </div>
          </Card>

          <Card title="Capture conditions" hint="Recorded with every photo so results can be compared across conditions.">
            <div className="form-grid">
              <div className="field">
                <span className="label" id="cap-l">Light at the sampling board</span>
                <Segmented name="capture" label="Light at the sampling board" value={capture} onChange={setCapture} options={CAPTURE} />
              </div>
              <div className="field">
                <span className="label">Weather</span>
                <Segmented name="weather" label="Weather" value={weather} onChange={setWeather} options={WEATHER} />
              </div>
              <Field label="Phone model" htmlFor="phone" help="Remembered on this device.">
                <input id="phone" className="input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="e.g. Samsung Galaxy A15" autoComplete="off" />
              </Field>
            </div>
          </Card>

          {err && <Notice kind="error">{err}</Notice>}
          <div className="sticky-actions">
            <Button type="submit" className="primary block" busy={busy} icon={ChevronRight}>Start round</Button>
          </div>
        </form>
      )}
    </>
  );
}

function QcList({ checks }) {
  return (
    <ul className="checklist">
      {checks.map((c) => (
        <li key={c.key}>
          {c.passed ? <CheckCircle2 size={20} className="ok" aria-label="passed" /> : <XCircle size={20} className="no" aria-label="failed" />}
          <span>{c.label}{!c.passed && <span className="subtle" style={{ display: 'block' }}>{c.hint}</span>}</span>
          <span className="val">{typeof c.value === 'number' ? fmtNum(c.value, 1) : c.value}</span>
        </li>
      ))}
    </ul>
  );
}

function FishResult({ fish, onNext }) {
  const qcOk = fish.quality?.passed;
  return (
    <Card className={`result-card fade-in ${fish.flagged ? 'bad' : 'good'}`} title={`Fish #${fish.seq} saved`} icon={CheckCircle2}>
      <div className="stats" style={{ marginBottom: 14 }}>
        <div className="stat"><div className="stat-label">Condition factor K</div><div className="stat-value">{fmtNum(fish.condition_factor, 2)}</div></div>
        <div className="stat"><div className="stat-label">Condition index (FCI)</div><div className="stat-value">{fmtNum(fish.fci, 2)}<small>/ 5</small></div></div>
        <div className="stat"><div className="stat-label">Image length</div><div className="stat-value">{fmtNum(fish.image_length_cm, 1)}<small>cm</small></div></div>
      </div>
      {fish.flagged && (
        <Notice kind="error"><Flag size={14} aria-hidden="true" style={{ verticalAlign: '-2px' }} /> <strong>Set this fish aside</strong> for the technician's review. Its visible condition indicators are below the threshold.</Notice>
      )}
      {fish.quality && (
        <>
          <h3 style={{ margin: '14px 0 6px' }}>Image check {qcOk ? '· passed' : '· retake recommended'}</h3>
          <QcList checks={fish.quality.checks} />
        </>
      )}
      {fish.detection?.is_stub && (
        <p className="subtle" style={{ marginTop: 10 }}>Indicators from the placeholder detector until YOLO26 is trained.</p>
      )}
      {!fish.photo_url && <p className="subtle" style={{ marginTop: 10 }}>No photo: weight and length recorded; condition index needs a photo.</p>}
      <div style={{ marginTop: 14 }}>
        <Button className="primary block" icon={Plus} onClick={onNext}>Next fish</Button>
      </div>
    </Card>
  );
}

export function SampleRound() {
  const { roundId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data: round, error, loading, reload } = useResource(`/api/rounds/${roundId}`);
  const [photo, setPhoto] = useState(null);
  const [preview, setPreview] = useState(null);
  const [weight, setWeight] = useState('');
  const [length, setLength] = useState('');
  const [score, setScore] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [result, setResult] = useState(null);
  const [formErr, setFormErr] = useState(null);
  const weightRef = useRef(null);

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  if (loading && !round) return <Loading label="Loading round" />;
  if (error && !round) return <LoadError error={error} onRetry={reload} />;
  if (round.status === 'completed') {
    return (
      <Card>
        <Empty icon={ClipboardCheck} title="This round is already recorded" action={<Link className="btn primary" to={`/rounds/${round.id}`}>View results</Link>} />
      </Card>
    );
  }

  const pickPhoto = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (preview) URL.revokeObjectURL(preview);
    setPhoto(file);
    setPreview(URL.createObjectURL(file));
  };

  const validate = () => {
    const errs = {};
    const w = Number(weight);
    const l = Number(length);
    if (!weight || !(w > 0) || w > 5000) errs.weight = 'Enter the weight from the scale in grams.';
    if (!length || !(l > 0) || l > 80) errs.length = 'Enter the ruler length in centimeters.';
    if (score && !(Number(score) >= 1 && Number(score) <= 5)) errs.score = 'Score must be between 1 and 5.';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setBusy(true);
    setFormErr(null);
    const fd = new FormData();
    fd.append('weight_g', weight);
    fd.append('length_cm', length);
    if (score) fd.append('technician_score', score);
    if (photo) fd.append('photo', photo);
    try {
      const fish = await api.form(`/api/rounds/${round.id}/fish`, fd);
      setResult(fish);
      reload();
    } catch (ex) {
      setFormErr(ex.message);
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    setResult(null);
    setPhoto(null);
    setPreview(null);
    setWeight('');
    setLength('');
    setScore('');
    setErrors({});
    setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 0);
  };

  const finish = async () => {
    setFinishing(true);
    try {
      await api.post(`/api/rounds/${round.id}/complete`);
      toast('Sampling round recorded');
      navigate(`/rounds/${round.id}`);
    } catch (ex) {
      setFormErr(ex.message);
      setFinishing(false);
    }
  };

  const n = round.fish.length;

  return (
    <>
      <div>
        <Link to={`/rounds/${round.id}`} className="back-link"><ArrowLeft size={16} aria-hidden="true" />Round overview</Link>
        <div className="page-head">
          <div>
            <Steps step={2} />
            <h1 style={{ marginTop: 10 }}>{round.pond.name} · fish #{n + 1}</h1>
            <p>Day {fmtNum(round.days_of_culture, 0)} · {round.capture_condition || 'capture not set'} · {n} fish recorded</p>
          </div>
        </div>
      </div>

      <div className="grid-main">
        <div className="grid" style={{ alignContent: 'start' }}>
          {result ? <FishResult fish={result} onNext={next} /> : (
            <form onSubmit={submit} className="grid" noValidate>
              <Card title="Photo" icon={Camera} hint="Whole body on the board, scale and color card in frame.">
                <label className="photo-drop">
                  <input type="file" accept="image/*" capture="environment" onChange={pickPhoto} aria-label="Take or choose a photo of the fish" />
                  {preview ? <img src={preview} alt="Selected fish photo preview" /> : (
                    <span className="ph-inner">
                      <ImagePlus size={34} aria-hidden="true" />
                      <strong style={{ color: 'var(--text)' }}>Tap to take a photo</strong>
                      <span className="small">or choose one from the gallery</span>
                    </span>
                  )}
                </label>
                <ul className="capture-tips" style={{ marginTop: 12 }}>
                  <li>Lay the fish flat, head to the left, on the standard board.</li>
                  <li>Keep the printed scale and color card fully visible.</li>
                  <li>Shade the board from direct sun to avoid glare.</li>
                </ul>
                {preview && <button type="button" className="btn sm ghost" style={{ marginTop: 8 }} onClick={() => { setPhoto(null); setPreview(null); }}>Remove photo</button>}
              </Card>

              <Card title="Measurements" icon={Fish}>
                <div className="form-grid two">
                  <Field label="Weight (scale)" htmlFor="w" error={errors.weight}>
                    <div className="input-unit">
                      <input ref={weightRef} id="w" className="input" type="number" inputMode="decimal" step="0.1" min="0"
                        value={weight} onChange={(e) => setWeight(e.target.value)} aria-invalid={!!errors.weight}
                        aria-describedby={errors.weight ? 'w-error' : undefined} required />
                      <span>g</span>
                    </div>
                  </Field>
                  <Field label="Length (ruler)" htmlFor="l" error={errors.length}>
                    <div className="input-unit">
                      <input id="l" className="input" type="number" inputMode="decimal" step="0.1" min="0"
                        value={length} onChange={(e) => setLength(e.target.value)} aria-invalid={!!errors.length}
                        aria-describedby={errors.length ? 'l-error' : undefined} required />
                      <span>cm</span>
                    </div>
                  </Field>
                </div>
                <details className="disclosure" style={{ marginTop: 8 }}>
                  <summary><ChevronRight size={16} aria-hidden="true" />Technician condition score (optional)</summary>
                  <Field label="Score, 1 (poor) to 5 (excellent)" htmlFor="s" error={errors.score} help="Entered by the technician; used to fit and evaluate the condition index.">
                    <input id="s" className="input" type="number" inputMode="decimal" step="0.5" min="1" max="5"
                      value={score} onChange={(e) => setScore(e.target.value)} aria-invalid={!!errors.score} />
                  </Field>
                </details>
              </Card>

              {formErr && <Notice kind="error">{formErr}</Notice>}
              <div className="sticky-actions">
                <Button type="submit" className="primary block" busy={busy} icon={CheckCircle2}>
                  {busy ? 'Analyzing…' : photo ? 'Save & analyze fish' : 'Save fish without photo'}
                </Button>
              </div>
            </form>
          )}
        </div>

        <Card title={`This round (${n})`} icon={ClipboardCheck}
          actions={<Button className="primary sm" busy={finishing} onClick={finish} disabled={!n}>Finish round</Button>}>
          {n === 0 ? <p className="subtle">Fish you save appear here. Aim for at least 10 per round.</p> : (
            <ul className="fish-mini">
              {[...round.fish].reverse().map((f) => (
                <li key={f.id}>
                  {f.photo_url ? <img className="thumb" src={f.photo_url} alt="" /> : <span className="thumb-ph"><Camera size={14} aria-hidden="true" /></span>}
                  <span><strong>#{f.seq}</strong> · {fmtNum(f.weight_g, 0)} g · {fmtNum(f.length_cm, 1)} cm</span>
                  {f.flagged ? <span className="badge tone-critical"><Flag size={12} aria-hidden="true" />Aside</span>
                    : <span className="mono small">{f.fci != null ? `FCI ${fmtNum(f.fci, 1)}` : 'K ' + fmtNum(f.condition_factor, 2)}</span>}
                </li>
              ))}
            </ul>
          )}
          {n > 0 && n < 10 && <p className="subtle" style={{ marginTop: 10 }}>{10 - n} more fish recommended for a reliable readiness status.</p>}
          {!n && <span className="sr-only">Finish is disabled until at least one fish is saved.</span>}
          <p className="subtle" style={{ marginTop: 10 }}><CloudRain size={13} aria-hidden="true" style={{ verticalAlign: '-2px' }} /> Return the fish to the pond after measuring.</p>
        </Card>
      </div>
    </>
  );
}
