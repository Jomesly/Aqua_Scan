import { useEffect, useState } from 'react';
import {
  Archive, Database, Download, FileText, Plus, Printer, RotateCcw, Save, Scale, ScanLine, SlidersHorizontal,
  Upload, Users, Waves,
} from 'lucide-react';
import { Button, Card, Field, LoadError, Loading, Notice, useToast } from '../components/ui';
import { DemoTag, ProvisionalTag } from '../components/Status';
import { api, useResource } from '../lib/api';
import { ROLE_LABEL, useAuth } from '../lib/auth';
import { fmtDate, fmtDateTime, fmtNum } from '../lib/format';

const TABS = [
  { key: 'ponds', label: 'Ponds', icon: Waves },
  { key: 'users', label: 'Users', icon: Users },
  { key: 'cutoffs', label: 'Cutoffs', icon: SlidersHorizontal },
  { key: 'weight', label: 'Weight model', icon: Scale },
  { key: 'board', label: 'Board', icon: ScanLine },
  { key: 'backup', label: 'Backup', icon: Database },
  { key: 'content', label: 'FAQs & About', icon: FileText },
];

function useAction() {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const toast = useToast();
  const run = async (key, fn, ok) => {
    setBusy(key);
    setError(null);
    try {
      const r = await fn();
      if (ok) toast(ok);
      return r;
    } catch (e) { setError(e.message); return undefined; } finally { setBusy(null); }
  };
  return { busy, error, run, setError };
}

// ---------------------------------------------------------------- ponds
const EMPTY_POND = { name: '', location: '', setup: 'Earthen pond', stocked_at: '', stocked_count: '' };

function PondForm({ initial, onSave, onCancel, busy }) {
  const [p, setP] = useState(initial);
  const set = (k) => (e) => setP({ ...p, [k]: e.target.value });
  return (
    <form className="stack" onSubmit={(e) => { e.preventDefault(); onSave(p); }}>
      <div className="form-grid two">
        <Field label="Pond name" htmlFor="pn"><input id="pn" className="input" value={p.name} onChange={set('name')} required /></Field>
        <Field label="Location / site" htmlFor="pl"><input id="pl" className="input" value={p.location || ''} onChange={set('location')} /></Field>
        <Field label="Culture setup" htmlFor="ps"><input id="ps" className="input" value={p.setup || ''} onChange={set('setup')} /></Field>
        <Field label="Stocking date" htmlFor="pd"><input id="pd" type="date" className="input" value={p.stocked_at || ''} onChange={set('stocked_at')} /></Field>
        <Field label="Stocked number of fish" htmlFor="pc"><input id="pc" type="number" min="0" className="input" value={p.stocked_count ?? ''} onChange={set('stocked_count')} /></Field>
      </div>
      <div className="row">
        <Button type="submit" className="primary" icon={Save} busy={busy}>Save pond</Button>
        {onCancel && <button type="button" className="btn ghost" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}

function Ponds() {
  const { data, error, loading, reload } = useResource('/api/ponds?include_archived=true');
  const [editing, setEditing] = useState(null);
  const act = useAction();
  if (loading && !data) return <Loading />;
  if (error) return <LoadError error={error} onRetry={reload} />;
  const clean = (p) => ({ ...p, stocked_count: p.stocked_count === '' ? null : Number(p.stocked_count), stocked_at: p.stocked_at || null });
  const save = async (p) => {
    const body = clean({ name: p.name, location: p.location, setup: p.setup, stocked_at: p.stocked_at, stocked_count: p.stocked_count });
    const ok = await act.run('save', () => (p.id ? api.patch(`/api/ponds/${p.id}`, body) : api.post('/api/ponds', body)), 'Pond saved');
    if (ok) { setEditing(null); reload(); }
  };
  const archive = async (p) => {
    await act.run(p.id, () => api.patch(`/api/ponds/${p.id}`, { archived: !p.archived }), p.archived ? 'Pond restored' : 'Pond archived');
    reload();
  };
  return (
    <div className="stack">
      {act.error && <Notice kind="error">{act.error}</Notice>}
      {editing ? (
        <Card title={editing.id ? `Edit ${editing.name}` : 'Add pond'}>
          <PondForm initial={editing} onSave={save} onCancel={() => setEditing(null)} busy={act.busy === 'save'} />
        </Card>
      ) : <div><Button className="primary" icon={Plus} onClick={() => setEditing(EMPTY_POND)}>Add pond</Button></div>}
      <Card flush>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Pond</th><th>Setup</th><th>Stocked</th><th className="num">Fish</th><th /></tr></thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id} className={p.archived ? 'muted' : ''}>
                  <td><strong>{p.name}</strong>{p.source === 'demo' && <DemoTag />}{p.archived && <span className="tag">Archived</span>}</td>
                  <td>{p.setup || '—'}</td><td>{fmtDate(p.stocked_at)}</td>
                  <td className="num">{p.stocked_count?.toLocaleString() ?? '—'}</td>
                  <td className="row gap-s">
                    <button type="button" className="btn sm" onClick={() => setEditing(p)}>Edit</button>
                    <button type="button" className="btn sm ghost" onClick={() => archive(p)}>
                      <Archive size={14} aria-hidden="true" />{p.archived ? 'Restore' : 'Archive'}</button>
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

// ---------------------------------------------------------------- users
function UsersTab() {
  const { user: me } = useAuth();
  const { data, error, loading, reload } = useResource('/api/users');
  const [form, setForm] = useState({ username: '', full_name: '', role: 'caretaker', password: '' });
  const act = useAction();
  if (loading && !data) return <Loading />;
  if (error) return <LoadError error={error} onRetry={reload} />;
  const create = async (e) => {
    e.preventDefault();
    const ok = await act.run('create', () => api.post('/api/users', form), 'User added');
    if (ok) { setForm({ username: '', full_name: '', role: 'caretaker', password: '' }); reload(); }
  };
  const patch = async (u, body, msg) => { await act.run(u.id, () => api.patch(`/api/users/${u.id}`, body), msg); reload(); };
  const resetPw = (u) => {
    const pw = window.prompt(`New password for ${u.username} (at least 6 characters):`);
    if (pw) patch(u, { password: pw }, 'Password reset');
  };
  return (
    <div className="stack">
      {act.error && <Notice kind="error">{act.error}</Notice>}
      <Card title="Add user">
        <form className="form-grid two" onSubmit={create}>
          <Field label="Username" htmlFor="un"><input id="un" className="input" value={form.username} autoCapitalize="none" onChange={(e) => setForm({ ...form, username: e.target.value })} required /></Field>
          <Field label="Full name" htmlFor="fn"><input id="fn" className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
          <Field label="Role" htmlFor="ro">
            <select id="ro" className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <Field label="Temporary password" htmlFor="pw" help="At least 6 characters. Ask the user to change it.">
            <input id="pw" className="input" type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          </Field>
          <div><Button type="submit" className="primary" icon={Plus} busy={act.busy === 'create'}>Add user</Button></div>
        </form>
      </Card>
      <Card flush>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>User</th><th>Role</th><th>Status</th><th /></tr></thead>
            <tbody>
              {data.map((u) => (
                <tr key={u.id}>
                  <td><strong>{u.username}</strong><div className="subtle">{u.full_name}</div></td>
                  <td>
                    <select className="select sm" aria-label={`Role of ${u.username}`} value={u.role}
                      onChange={(e) => patch(u, { role: e.target.value }, 'Role changed')}>
                      {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                  </td>
                  <td>{u.active ? 'Active' : <span className="tag">Deactivated</span>}</td>
                  <td className="row gap-s">
                    <button type="button" className="btn sm" onClick={() => resetPw(u)}>Reset password</button>
                    {u.id !== me.id && (
                      <button type="button" className="btn sm ghost" onClick={() => patch(u, { active: !u.active }, u.active ? 'User deactivated' : 'User activated')}>
                        {u.active ? 'Deactivate' : 'Activate'}</button>
                    )}
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

// ---------------------------------------------------------------- cutoffs
const GROUP_TITLES = {
  health: 'Disease screening and Health status',
  harvest: 'Harvest readiness',
  weight: 'Weight estimation',
  board: 'Sampling board',
};
const PERCENT_KEYS = ['det_conf', 'referral_conf', 'pond_watch_share', 'pond_refer_share', 'approaching_share', 'ready_share', 'max_cv'];

function Cutoffs() {
  const { data, error, loading, reload } = useResource('/api/thresholds');
  const [vals, setVals] = useState(null);
  const [confirmed, setConfirmed] = useState(false);
  const act = useAction();
  useEffect(() => { if (data) { setVals(data.values); setConfirmed(data.confirmed); } }, [data]);
  if (loading && !data) return <Loading />;
  if (error) return <LoadError error={error} onRetry={reload} />;
  if (!vals) return null;
  const save = async () => {
    const ok = await act.run('save', () => api.put('/api/thresholds', { values: vals, confirmed }), 'Cutoffs saved');
    if (ok) reload();
  };
  const changed = Object.keys(vals).some((k) => Number(vals[k]) !== data.values[k]) || confirmed !== data.confirmed;
  return (
    <div className="stack">
      <Notice kind={data.confirmed ? 'success' : 'warn'}>
        {data.confirmed
          ? 'These cutoffs are marked as confirmed with the BFAR technician.'
          : <>These cutoffs are <strong>provisional</strong>. The study sets them with the BFAR technician from the first sampling rounds.</>}
        {' '}Changes apply to draft rounds immediately. Completed rounds keep the cutoffs they were assessed with.
      </Notice>
      {act.error && <Notice kind="error">{act.error}</Notice>}
      {Object.entries(data.groups).map(([g, keys]) => (
        <Card key={g} title={GROUP_TITLES[g]}>
          <div className="form-grid two">
            {keys.map((k) => (
              <Field key={k} label={data.labels[k]} htmlFor={`t-${k}`}
                help={`Default ${data.defaults[k]}${PERCENT_KEYS.includes(k) ? ` (${Math.round(data.defaults[k] * 100)} %)` : ''}`}>
                <input id={`t-${k}`} className="input" type="number" step="any" value={vals[k]}
                  onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
              </Field>
            ))}
          </div>
        </Card>
      ))}
      <label className="toggle">
        <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
        These values were confirmed with the BFAR technician
      </label>
      <div className="sticky-actions">
        <Button className="primary" icon={Save} busy={act.busy === 'save'} disabled={!changed} onClick={save}>Save cutoffs</Button>
        <button type="button" className="btn ghost" onClick={() => setVals(data.defaults)}><RotateCcw size={16} aria-hidden="true" />Load defaults</button>
      </div>
      <Card title="Change history" flush>
        {data.history.length === 0 ? <p className="card-pad muted">No changes yet.</p> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>When</th><th>Who</th><th>Changes</th><th>Confirmed</th></tr></thead>
              <tbody>
                {data.history.map((h) => (
                  <tr key={h.id}>
                    <td>{fmtDateTime(h.ts)}</td><td>{h.user}</td>
                    <td className="small">{Object.entries(h.changes).map(([k, [a, b]]) => `${data.labels[k] || k}: ${a} → ${b}`).join('; ') || '—'}</td>
                    <td>{h.confirmed ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- weight model
function WeightModel() {
  const { data, error, loading, reload } = useResource('/api/weight-model');
  const [demo, setDemo] = useState(false);
  const act = useAction();
  if (loading && !data) return <Loading />;
  if (error) return <LoadError error={error} onRetry={reload} />;
  const fit = async () => { if (await act.run('fit', () => api.post('/api/weight-model/fit', { include_demo: demo }), 'Weight model fitted')) reload(); };
  const reset = async () => {
    if (!window.confirm('Go back to the provisional length–weight curve?')) return;
    await act.run('reset', () => api.post('/api/weight-model/reset'), 'Using the provisional curve');
    reload();
  };
  const f = data.last_fit;
  const rows = demo ? data.available_rows.including_demo : data.available_rows.real;
  return (
    <div className="stack">
      <Card title="Active weight model">
        <p><strong>{data.active.label}</strong> {data.active.provisional && <ProvisionalTag />}</p>
        {data.active.terms && <p className="small muted">Terms: <span className="mono">{data.active.terms.join(', ')}</span>
          {data.active.range_L && ` · valid for fish ${data.active.range_L[0]}–${data.active.range_L[1]} cm`}</p>}
        <p className="subtle" style={{ marginTop: 8 }}>The weight regression uses the image length (L) and area (A) of each fish and its facility-scale weight as the
          reference: a linear baseline and a degree-2 model with backward elimination, compared by grouped cross-validation.</p>
      </Card>
      <Card title="Fit from recorded fish">
        <p>{rows} fish have a scale weight together with an image length and area. At least {data.min_rows} are needed.</p>
        <label className="toggle"><input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} />Include demo data</label>
        {act.error && <Notice kind="error">{act.error}</Notice>}
        <div className="row wrap" style={{ marginTop: 12 }}>
          <Button className="primary" icon={Scale} busy={act.busy === 'fit'} disabled={rows < data.min_rows} onClick={fit}>Fit weight model</Button>
          {!data.active.provisional && <Button className="ghost" icon={RotateCcw} busy={act.busy === 'reset'} onClick={reset}>Use provisional curve</Button>}
        </div>
      </Card>
      {f && (
        <Card title="Last fit" hint={`${fmtDateTime(data.last_fit_at)} · ${f.n} fish · ${f.cv_scheme}`} flush>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Model</th><th>Terms</th><th className="num">CV R²</th><th className="num">CV RMSE g</th><th className="num">CV MARE %</th></tr></thead>
              <tbody>
                {['linear', 'poly'].map((k) => (
                  <tr key={k}><td>{f[k].label}{f.selected === k && <span className="tag good">selected</span>}</td>
                    <td className="mono xs">{f[k].terms.join(', ')}</td><td className="num">{fmtNum(f[k].cv.r2, 3)}</td>
                    <td className="num">{fmtNum(f[k].cv.rmse, 1)}</td><td className="num">{fmtNum(f[k].cv.mare, 1)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- board
function Board() {
  const { data } = useResource('/api/thresholds');
  const t = data?.values;
  return (
    <div className="stack">
      <Card title="Printable sampling board" icon={ScanLine}>
        <p>Four ArUco markers (ids 0–3) mark the corners of the measurement rectangle. The inner rectangle is currently
          <strong> {t ? `${t.board_width_cm} × ${t.board_height_cm} cm` : '…'}</strong>. Change it under Cutoffs → Sampling board.</p>
        <ol className="small" style={{ marginTop: 8 }}>
          <li>Download the PDF and print it at <strong>100 % / actual size</strong> (no “fit to page”). A3 landscape fits the default size.</li>
          <li>Glue it to a flat, matte board. Measure the inner rectangle with a ruler, and enter the measured size if it differs.</li>
          <li>Keep all four markers uncovered and dry. Place the whole fish inside the rectangle.</li>
        </ol>
        <div className="row wrap" style={{ marginTop: 12 }}>
          <a className="btn primary" href="/api/board.pdf"><Printer size={18} aria-hidden="true" />Download PDF</a>
          <a className="btn" href="/api/board.png" target="_blank" rel="noreferrer"><Download size={18} aria-hidden="true" />PNG preview</a>
        </div>
      </Card>
      <img className="board-preview" src="/api/board.png" alt="Sampling board with four corner markers" />
    </div>
  );
}

// ---------------------------------------------------------------- backup
function Backup() {
  const act = useAction();
  const [file, setFile] = useState(null);
  const restore = async () => {
    if (!file || !window.confirm('Restoring replaces ALL current records and photos with the backup. Continue?')) return;
    const fd = new FormData();
    fd.append('file', file);
    if (await act.run('restore', () => api.form('/api/restore', fd), 'Backup restored')) window.location.assign('/');
  };
  return (
    <div className="grid-2">
      <Card title="Back up" icon={Download}>
        <p>Downloads one .zip with the database (ponds, rounds, fish, users, cutoffs, models) and all photos.</p>
        <a className="btn primary" href="/api/backup" style={{ marginTop: 12 }}><Download size={18} aria-hidden="true" />Download backup</a>
      </Card>
      <Card title="Restore" icon={Upload}>
        <p>Replaces everything with the contents of a Tilapiers backup.</p>
        <input type="file" accept=".zip" className="input" style={{ marginTop: 12 }} onChange={(e) => setFile(e.target.files?.[0] || null)} aria-label="Backup file" />
        {act.error && <Notice kind="error">{act.error}</Notice>}
        <Button className="danger" icon={Upload} busy={act.busy === 'restore'} disabled={!file} onClick={restore} style={{ marginTop: 12 }}>Restore backup</Button>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- content
function ContentEditor() {
  const { data, error, loading, reload } = useResource('/api/content');
  const [key, setKey] = useState('faqs');
  const [draft, setDraft] = useState(null);
  const act = useAction();
  useEffect(() => { if (data) setDraft(data.find((c) => c.key === key) || { key, title: '', body_md: '' }); }, [data, key]);
  if (loading && !data) return <Loading />;
  if (error) return <LoadError error={error} onRetry={reload} />;
  if (!draft) return null;
  const save = async () => { if (await act.run('save', () => api.put(`/api/content/${key}`, { title: draft.title, body_md: draft.body_md }), 'Page saved')) reload(); };
  return (
    <Card title="Edit help pages" hint="Simple formatting: ## heading, - list item, **bold**, *italic*.">
      <div className="row wrap" role="tablist" aria-label="Page">
        {[['faqs', 'FAQs'], ['about', 'About Us']].map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={key === k} className="tab" onClick={() => setKey(k)}>{l}</button>
        ))}
      </div>
      <Field label="Title" htmlFor="ct"><input id="ct" className="input" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></Field>
      <Field label="Content" htmlFor="cb"><textarea id="cb" className="textarea mono" rows={18} value={draft.body_md} onChange={(e) => setDraft({ ...draft, body_md: e.target.value })} /></Field>
      {act.error && <Notice kind="error">{act.error}</Notice>}
      <Button className="primary" icon={Save} busy={act.busy === 'save'} onClick={save}>Save page</Button>
    </Card>
  );
}

const PANELS = { ponds: Ponds, users: UsersTab, cutoffs: Cutoffs, weight: WeightModel, board: Board, backup: Backup, content: ContentEditor };

export default function Maintenance() {
  const [tab, setTab] = useState(() => new URLSearchParams(window.location.search).get('tab') || 'ponds');
  const Panel = PANELS[tab] || Ponds;
  const select = (k) => { setTab(k); window.history.replaceState(null, '', `?tab=${k}`); };
  return (
    <div className="stack">
      <div className="page-head">
        <span className="eyebrow">Administrator</span>
        <h1>Maintenance</h1>
        <p>Ponds and stocking, user accounts, status cutoffs, the weight model, the sampling board, and backups.</p>
      </div>
      <div className="tabs scroll" role="tablist" aria-label="Maintenance sections">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className="tab" onClick={() => select(key)}>
            <Icon size={16} aria-hidden="true" />{label}
          </button>
        ))}
      </div>
      <Panel />
    </div>
  );
}
