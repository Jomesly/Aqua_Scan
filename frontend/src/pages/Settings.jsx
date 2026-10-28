import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Bell, Cpu, Fish, Lock, Plus, Send, SlidersHorizontal } from 'lucide-react';
import { api, useResource } from '../lib/api';
import { fmtDate, fmtNum, fromLocalInput, toLocalInput } from '../lib/format';
import { Button, Card, Field, LoadError, Loading, Notice, useToast } from '../components/ui';
import { useSystem } from '../components/Shell';

const LABELS = {
  temp_min_c: ['Safe band minimum', '°C'],
  temp_max_c: ['Safe band maximum', '°C'],
  temp_moderate_margin_c: ['Moderate margin outside band', '°C'],
  do_good_min_ppm: ['Dissolved oxygen, Good at least', 'ppm'],
  do_critical_below_ppm: ['Dissolved oxygen, Critical below', 'ppm'],
  algae_report_valid_days: ['Algae report stays active for', 'days'],
  sensor_stale_after_s: ['Probe offline after no reading for', 's'],
  fci_flag_below: ['Flag fish with FCI below', '/ 5'],
  health_watch_share: ['Watch when flagged share reaches', '0–1'],
  health_refer_share: ['Refer when flagged share reaches', '0–1'],
  condition_factor_low: ['Low condition factor K below', ''],
  target_weight_g: ['Target market size', 'g'],
  ready_share_at_target: ['Ready when share at target reaches', '0–1'],
  approaching_share_at_target: ['Approaching when share reaches', '0–1'],
  max_weight_cv: ['Max weight CV for uniformity', ''],
  culture_days_min: ['Usual culture period from', 'days'],
  culture_days_max: ['Usual culture period to', 'days'],
  growth_poly_min_rounds: ['Rounds needed for growth curve', ''],
  recent_critical_days: ['Recent Critical window', 'days'],
  min_fish_per_round: ['Recommended fish per round', ''],
};
const GROUP_TITLES = { environment: 'Environment', health: 'Fish health', harvest: 'Harvest readiness' };

function useHashScroll() {
  const { hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    const el = document.getElementById(hash.slice(1));
    if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  }, [hash]);
}

function PondsSection() {
  const { data: ponds, reload } = useResource('/api/ponds?include_archived=true');
  const [form, setForm] = useState({ name: '', stocked_at: toLocalInput(Date.now() / 1000), stocked_count: '', area_m2: '', feeding_regime: '', location: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const toast = useToast();

  const add = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { setErr('Give the pond a name.'); return; }
    setBusy(true);
    setErr(null);
    try {
      await api.post('/api/ponds', {
        name: form.name.trim(), stocked_at: fromLocalInput(form.stocked_at),
        stocked_count: form.stocked_count ? Number(form.stocked_count) : null,
        area_m2: form.area_m2 ? Number(form.area_m2) : null,
        feeding_regime: form.feeding_regime || null, location: form.location || null,
      });
      toast(`${form.name} added`);
      setForm({ ...form, name: '', stocked_count: '', area_m2: '', location: '' });
      reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };
  const toggleArchive = async (p) => {
    await api.patch(`/api/ponds/${p.id}`, { archived: p.archived ? 0 : 1 });
    reload();
  };

  return (
    <Card title="Ponds" icon={Fish} hint="Days of culture are counted from the stocking date.">
      <div id="ponds" style={{ scrollMarginTop: 80 }} />
      {ponds?.length > 0 && (
        <div className="table-wrap" style={{ marginBottom: 16 }}>
          <table className="data">
            <thead><tr><th>Name</th><th>Stocked</th><th className="num">Day</th><th className="num">Fish</th><th>Feeding</th><th /></tr></thead>
            <tbody>
              {ponds.map((p) => (
                <tr key={p.id}>
                  <td><strong>{p.name}</strong>{p.archived ? <span className="tag" style={{ marginLeft: 6 }}>Archived</span> : null}</td>
                  <td>{fmtDate(p.stocked_at)}</td>
                  <td className="num">{fmtNum(p.days_of_culture, 0)}</td>
                  <td className="num">{p.stocked_count ?? '—'}</td>
                  <td>{p.feeding_regime || '—'}</td>
                  <td><button type="button" className="btn sm ghost" onClick={() => toggleArchive(p)}>{p.archived ? 'Restore' : 'Archive'}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form onSubmit={add} className="stack" noValidate>
        <h3>Add a pond</h3>
        <div className="form-grid two">
          <Field label="Name" htmlFor="p-name"><input id="p-name" className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
          <Field label="Stocking date and time" htmlFor="p-stock"><input id="p-stock" className="input" type="datetime-local" value={form.stocked_at} onChange={(e) => setForm({ ...form, stocked_at: e.target.value })} /></Field>
          <Field label="Fish stocked" htmlFor="p-count"><input id="p-count" className="input" type="number" inputMode="numeric" min="0" value={form.stocked_count} onChange={(e) => setForm({ ...form, stocked_count: e.target.value })} /></Field>
          <Field label="Area" htmlFor="p-area"><div className="input-unit"><input id="p-area" className="input" type="number" inputMode="decimal" min="0" value={form.area_m2} onChange={(e) => setForm({ ...form, area_m2: e.target.value })} /><span>m²</span></div></Field>
          <Field label="Feeding regime" htmlFor="p-feed"><input id="p-feed" className="input" value={form.feeding_regime} onChange={(e) => setForm({ ...form, feeding_regime: e.target.value })} placeholder="e.g. Pellets, 2x daily" /></Field>
          <Field label="Location" htmlFor="p-loc"><input id="p-loc" className="input" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></Field>
        </div>
        {err && <Notice kind="error">{err}</Notice>}
        <Button type="submit" className="primary" icon={Plus} busy={busy} style={{ justifySelf: 'start' }}>Add pond</Button>
      </form>
    </Card>
  );
}

function ThresholdsSection() {
  const { data, error, reload } = useResource('/api/settings/thresholds');
  const [values, setValues] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const toast = useToast();
  const { reloadSystem } = useSystem();

  useEffect(() => { if (data) setValues(data.values); }, [data]);
  if (error) return <LoadError error={error} onRetry={reload} />;
  if (!values) return <Loading />;

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const body = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v === '' ? null : Number(v)]));
      await api.put('/api/settings/thresholds', body);
      toast('Thresholds saved');
      reload();
      reloadSystem();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Rule thresholds" icon={SlidersHorizontal}
      hint="The 24–31 °C band is fixed by the study team. Every other value is provisional until set with a BFAR technician (Chapter 3).">
      <form onSubmit={save} className="stack">
        {Object.entries(data.groups).map(([group, keys]) => (
          <fieldset key={group} style={{ border: 0, padding: 0, margin: '0 0 8px' }}>
            <legend style={{ fontWeight: 600, marginBottom: 10 }}>{GROUP_TITLES[group]}</legend>
            <div className="form-grid two">
              {keys.map((k) => {
                const fixed = data.fixed.includes(k);
                const [label, unit] = LABELS[k] || [k, ''];
                return (
                  <Field key={k} label={<>{label} {fixed ? <span className="tag"><Lock size={11} aria-hidden="true" />fixed</span> : <span className="tag warn">provisional</span>}</>} htmlFor={`t-${k}`}>
                    <div className="input-unit">
                      <input id={`t-${k}`} className="input" type="number" step="any" inputMode="decimal" value={values[k]}
                        readOnly={fixed} aria-readonly={fixed} style={fixed ? { background: 'var(--surface-2)' } : undefined}
                        onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
                      {unit && <span>{unit}</span>}
                    </div>
                  </Field>
                );
              })}
            </div>
          </fieldset>
        ))}
        {err && <Notice kind="error">{err}</Notice>}
        <Button type="submit" className="primary" busy={busy} style={{ justifySelf: 'start' }}>Save thresholds</Button>
      </form>
    </Card>
  );
}

function NotificationsSection() {
  const { data, reload } = useResource('/api/settings/contact');
  const [contact, setContact] = useState(null);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const toast = useToast();
  useEffect(() => { if (data) setContact(data.contact); }, [data]);
  if (!data || !contact) return <Loading />;

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.put('/api/settings/contact', contact);
      toast('Contact saved');
      reload();
    } finally {
      setBusy(false);
    }
  };
  const test = async () => {
    setTesting(true);
    try {
      setTestResult(await api.post('/api/notifications/test'));
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card title="Notifications" icon={Bell} hint="Email or SMS is still being decided; the channel is set on the server (TILAPIERS_NOTIFY_CHANNEL).">
      <div id="notifications" style={{ scrollMarginTop: 80 }} />
      <Notice kind={data.ready ? 'success' : 'info'}>
        <strong>Channel: {data.channel === 'none' ? 'dashboard only' : data.channel}.</strong> {data.detail}
      </Notice>
      <form onSubmit={save} className="stack" style={{ marginTop: 16 }}>
        <div className="form-grid two">
          <Field label="Caretaker name" htmlFor="c-name"><input id="c-name" className="input" value={contact.name} onChange={(e) => setContact({ ...contact, name: e.target.value })} autoComplete="name" /></Field>
          <Field label="Email" htmlFor="c-email"><input id="c-email" className="input" type="email" value={contact.email} onChange={(e) => setContact({ ...contact, email: e.target.value })} autoComplete="email" /></Field>
          <Field label="Mobile number" htmlFor="c-phone" help="Kept for SMS if that channel is chosen."><input id="c-phone" className="input" type="tel" value={contact.phone} onChange={(e) => setContact({ ...contact, phone: e.target.value })} autoComplete="tel" placeholder="+63 9XX XXX XXXX" /></Field>
        </div>
        <div className="row">
          <Button type="submit" className="primary" busy={busy}>Save contact</Button>
          <Button type="button" icon={Send} busy={testing} onClick={test}>Send test alert</Button>
        </div>
        {testResult && (
          <Notice kind="info">
            Test alert recorded. Deliveries: {testResult.deliveries.map((d) => `${d.channel} ${d.status.replace('_', ' ')}${d.detail ? ` (${d.detail})` : ''}`).join(', ')}.
          </Notice>
        )}
      </form>
    </Card>
  );
}

function SystemSection() {
  const { system } = useSystem();
  if (!system) return null;
  const s = system.sensor || {};
  return (
    <Card title="System" icon={Cpu}>
      <div className="table-wrap">
        <table className="data">
          <tbody>
            <tr><td>Mode</td><td>{system.demo ? 'Demo (seeded and simulated data)' : 'Field'}</td></tr>
            <tr><td>Temperature source</td><td>{s.mode === 'simulate' ? 'Simulator' : s.mode === 'off' ? 'Network ingest only' : s.probe_port ? `USB probe on ${s.probe_port} → pond ${s.serial_pond_id}` : `Not connected${s.probe_error ? ` (${s.probe_error})` : ''}`}</td></tr>
            <tr><td>Fish detector</td><td>{system.detector.name}</td></tr>
            <tr><td>Condition index model</td><td>{system.fci_model.source}</td></tr>
            <tr><td>Season</td><td>{system.season}</td></tr>
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function Settings() {
  useHashScroll();
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>Ponds, rule thresholds, notifications and system status.</p>
        </div>
      </div>
      <PondsSection />
      <ThresholdsSection />
      <div className="grid-2">
        <NotificationsSection />
        <SystemSection />
      </div>
    </>
  );
}
