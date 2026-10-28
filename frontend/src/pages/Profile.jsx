import { useState } from 'react';
import { KeyRound, LogOut, Save } from 'lucide-react';
import { Button, Card, Field, Notice, useToast } from '../components/ui';
import { api } from '../lib/api';
import { ROLE_LABEL, useAuth } from '../lib/auth';

export default function Profile() {
  const { user, refresh, logout } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user.full_name || '');
  const [pw, setPw] = useState({ current_password: '', new_password: '', confirm: '' });
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  const saveName = async (e) => {
    e.preventDefault();
    setBusy('name');
    try {
      await api.patch('/api/profile', { full_name: name });
      await refresh();
      toast('Profile saved');
    } catch (err) { setError(err.message); } finally { setBusy(null); }
  };

  const savePw = async (e) => {
    e.preventDefault();
    setError(null);
    if (pw.new_password !== pw.confirm) { setError('The new passwords do not match.'); return; }
    setBusy('pw');
    try {
      await api.post('/api/profile/password', { current_password: pw.current_password, new_password: pw.new_password });
      setPw({ current_password: '', new_password: '', confirm: '' });
      toast('Password changed');
    } catch (err) { setError(err.message); } finally { setBusy(null); }
  };

  return (
    <div className="stack">
      <div className="page-head">
        <span className="eyebrow">Profile</span>
        <h1>{user.full_name}</h1>
        <p>Signed in as <strong>{user.username}</strong> · {ROLE_LABEL[user.role]}</p>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <div className="grid-2">
        <Card title="Your details">
          <form onSubmit={saveName} className="stack">
            <Field label="Full name" htmlFor="fullname">
              <input id="fullname" className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </Field>
            <Button type="submit" className="primary" busy={busy === 'name'} icon={Save}>Save</Button>
          </form>
        </Card>
        <Card title="Change password">
          <form onSubmit={savePw} className="stack">
            <Field label="Current password" htmlFor="cur">
              <input id="cur" type="password" className="input" autoComplete="current-password" value={pw.current_password}
                onChange={(e) => setPw({ ...pw, current_password: e.target.value })} required />
            </Field>
            <Field label="New password" htmlFor="new" help="At least 6 characters.">
              <input id="new" type="password" className="input" autoComplete="new-password" value={pw.new_password}
                onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required />
            </Field>
            <Field label="Repeat new password" htmlFor="rep">
              <input id="rep" type="password" className="input" autoComplete="new-password" value={pw.confirm}
                onChange={(e) => setPw({ ...pw, confirm: e.target.value })} required />
            </Field>
            <Button type="submit" className="primary" busy={busy === 'pw'} icon={KeyRound}>Change password</Button>
          </form>
        </Card>
      </div>
      <div><Button className="ghost" icon={LogOut} onClick={logout}>Log out</Button></div>
    </div>
  );
}
