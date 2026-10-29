import { useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { LogIn, Scale, ShieldCheck, Sprout } from 'lucide-react';
import { FishMark, ThemeToggle } from '../components/Shell';
import { Button, Field, Notice } from '../components/ui';
import { ROLE_LABEL, useAuth } from '../lib/auth';

export default function Login() {
  const { user, system, login } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const next = params.get('next') || '/';

  if (user) return <Navigate to={next.startsWith('/login') ? '/' : next} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(form.username, form.password);
      navigate(next.startsWith('/login') ? '/' : next, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <aside className="login-panel" aria-label="About Tilapiers">
        <div className="login-panel-brand">
          <span className="brand-mark lg"><FishMark size={30} /></span>
          <span>Tilapiers</span>
        </div>
        <div className="login-panel-copy">
          <h2>Fish health, weight and harvest readiness for outdoor Nile tilapia ponds.</h2>
          <ul>
            <li><ShieldCheck size={18} aria-hidden="true" />Screens each sampled fish for signs of Aeromonas and TiLV</li>
            <li><Scale size={18} aria-hidden="true" />Estimates weight from a photo on the measuring board</li>
            <li><Sprout size={18} aria-hidden="true" />Tracks growth toward harvest size, round by round</li>
          </ul>
        </div>
        <p className="login-panel-foot">College of Computer Studies · Technological Institute of the Philippines, in cooperation with BFAR</p>
      </aside>
      <main className="login-main">
        <div className="login-theme"><ThemeToggle /></div>
        <div className="login-card">
          <div className="login-brand">
            <span className="brand-mark lg"><FishMark size={30} /></span>
            <span>Tilapiers</span>
          </div>
          <div>
            <h1>Log in</h1>
            <p className="muted login-lede">Use the account your administrator set up for you.</p>
          </div>
          <form onSubmit={submit} className="stack" noValidate>
            <Field label="Username" htmlFor="username">
              <input id="username" className="input" autoComplete="username" autoCapitalize="none" required
                value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </Field>
            <Field label="Password" htmlFor="password">
              <input id="password" className="input" type="password" autoComplete="current-password" required
                value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </Field>
            {error && <Notice kind="error">{error}</Notice>}
            <Button type="submit" className="primary block" busy={busy} icon={LogIn}>Log in</Button>
          </form>
          {system?.demo_accounts?.length > 0 && (
            <div className="demo-accounts">
              <p className="subtle">Demo accounts. Tap one to fill in the form:</p>
              <div className="row wrap">
                {system.demo_accounts.map((a) => (
                  <button key={a.username} type="button" className="btn sm"
                    onClick={() => setForm({ username: a.username, password: a.password })}>
                    {ROLE_LABEL[a.role]}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <p className="subtle login-foot">College of Computer Studies · Technological Institute of the Philippines, in cooperation with BFAR</p>
      </main>
    </div>
  );
}
