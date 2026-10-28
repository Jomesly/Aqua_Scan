import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Camera, CloudSun, Images, Printer, ScanLine, Sun, Trees } from 'lucide-react';
import { Button, Card, Empty, Field, LoadError, Loading, Notice, Segmented } from '../components/ui';
import { DemoTag } from '../components/Status';
import { api, useResource } from '../lib/api';
import { fmtDate, todayIso } from '../lib/format';

function daysBetween(a, b) {
  if (!a || !b) return '';
  return Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 86400000));
}

export default function NewRound() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { data: ponds, error, loading, reload } = useResource('/api/ponds');
  const [form, setForm] = useState({
    pond_id: params.get('pond') ? Number(params.get('pond')) : null, sampled_at: todayIso(), days_of_culture: '',
    fish_count_n: '', board_mode: 'board', capture_condition: 'open sunlight', notes: '',
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const pond = useMemo(() => ponds?.find((p) => p.id === form.pond_id), [ponds, form.pond_id]);

  useEffect(() => {
    if (ponds?.length === 1 && !form.pond_id) setForm((f) => ({ ...f, pond_id: ponds[0].id }));
  }, [ponds, form.pond_id]);
  useEffect(() => {
    if (!pond) return;
    setForm((f) => ({ ...f, days_of_culture: daysBetween(pond.stocked_at, f.sampled_at),
      fish_count_n: pond.stocked_count ?? '' }));
  }, [pond]);

  if (loading && !ponds) return <Loading />;
  if (error) return <LoadError error={error} onRetry={reload} />;
  if (!ponds.length) return <Empty icon={Trees} title="No ponds yet">The administrator adds ponds in Maintenance.</Empty>;

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    if (!form.pond_id) { setErr('Choose the pond you are sampling.'); return; }
    setBusy(true);
    setErr(null);
    try {
      const r = await api.post('/api/rounds', {
        pond_id: form.pond_id, sampled_at: form.sampled_at,
        days_of_culture: form.days_of_culture === '' ? null : Number(form.days_of_culture),
        fish_count_n: form.fish_count_n === '' ? null : Number(form.fish_count_n),
        board_mode: form.board_mode === 'board', capture_condition: form.capture_condition, notes: form.notes || null,
      });
      navigate(`/rounds/${r.id}`);
    } catch (ex) { setErr(ex.message); setBusy(false); }
  };

  return (
    <form className="stack narrow" onSubmit={submit}>
      <div className="page-head">
        <span className="eyebrow">New sampling round</span>
        <h1>Which pond are you sampling?</h1>
        <p>After this you will photograph each fish on the board (both sides), then weigh and measure it.</p>
      </div>

      <div className="pond-pick" role="radiogroup" aria-label="Pond">
        {ponds.map((p) => (
          <label key={p.id}>
            <input type="radio" name="pond" checked={form.pond_id === p.id} onChange={() => setForm({ ...form, pond_id: p.id })} />
            <span><strong>{p.name}</strong>{p.source === 'demo' && <DemoTag />}
              <small>{p.stocked_at ? `Stocked ${fmtDate(p.stocked_at)}` : 'Stocking date not set'}</small></span>
          </label>
        ))}
      </div>

      <Card title="Round details">
        <div className="form-grid two">
          <Field label="Sampling date" htmlFor="date">
            <input id="date" type="date" className="input" value={form.sampled_at} max={todayIso()}
              onChange={(e) => setForm({ ...form, sampled_at: e.target.value,
                days_of_culture: pond ? daysBetween(pond.stocked_at, e.target.value) : form.days_of_culture })} />
          </Field>
          <Field label="Days of culture" htmlFor="doc" help={pond?.stocked_at ? 'Counted from the stocking date. Edit if needed.' : 'Days since stocking.'}>
            <input id="doc" type="number" min="0" inputMode="numeric" className="input" value={form.days_of_culture} onChange={set('days_of_culture')} />
          </Field>
          <Field label="Stocked or counted fish (N)" htmlFor="n" help="Used for the biomass estimate: average weight × N.">
            <input id="n" type="number" min="0" inputMode="numeric" className="input" value={form.fish_count_n} onChange={set('fish_count_n')} />
          </Field>
        </div>
      </Card>

      <Card title="Photographs">
        <Segmented name="mode" label="Photo source" value={form.board_mode} onChange={(v) => setForm({ ...form, board_mode: v })}
          options={[{ value: 'board', label: 'Sampling board', icon: ScanLine },
            { value: 'public', label: 'Public / test photos (no board)', icon: Images }]} />
        {form.board_mode === 'board' ? (
          <p className="subtle" style={{ marginTop: 8 }}>
            All four corner markers must be visible. They give every photo its scale, so length and weight can be measured.{' '}
            <a href="/api/board.pdf" target="_blank" rel="noreferrer"><Printer size={14} aria-hidden="true" style={{ verticalAlign: '-2px' }} /> Print the board</a>
          </p>
        ) : (
          <Notice kind="warn">Without the board there is no scale. Fish are <strong>screened only</strong>; length, weight and K show
            “No scale: not measured”, and harvest readiness cannot be assessed for this round.</Notice>
        )}
        <div style={{ marginTop: 12 }}>
          <span className="label-text">Capture condition</span>
          <Segmented name="cond" label="Capture condition" value={form.capture_condition}
            onChange={(v) => setForm({ ...form, capture_condition: v })}
            options={[{ value: 'open sunlight', label: 'Sunlight', icon: Sun },
              { value: 'shade', label: 'Shade', icon: Trees }, { value: 'overcast', label: 'Overcast', icon: CloudSun }]} />
        </div>
        <Field label="Notes (optional)" htmlFor="notes">
          <textarea id="notes" className="textarea" rows={2} value={form.notes} onChange={set('notes')} />
        </Field>
      </Card>

      {err && <Notice kind="error">{err}</Notice>}
      <div className="row wrap">
        <Button type="submit" className="primary" busy={busy} icon={Camera}>Start round</Button>
        <Link to="/" className="btn ghost">Cancel</Link>
      </div>
    </form>
  );
}
