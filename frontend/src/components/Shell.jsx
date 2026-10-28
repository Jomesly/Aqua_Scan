import { useEffect, useState } from 'react';
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  BookOpen, Camera, CircleHelp, ClipboardCheck, FlaskConical, Info, LayoutDashboard, LogOut, Moon,
  Stethoscope, Sun, UserRound, Wrench,
} from 'lucide-react';
import { useResource } from '../lib/api';
import { can, ROLE_LABEL, useAuth } from '../lib/auth';
import { Loading } from './ui';

export function FishMark({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none">
      <path d="M2.5 12c2.6-4.3 7.6-5.6 11-2.6L17 7v10l-3.5-2.4c-3.4 3-8.4 1.7-11-2.6z" fill="currentColor" />
      <circle cx="6.6" cy="11.2" r="1" fill="var(--primary)" />
      <path d="M17 7l4.5-2v14L17 17" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

export function ThemeToggle() {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute('data-theme') || 'light');
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('theme', theme); } catch { /* private mode */ }
  }, [theme]);
  const next = theme === 'dark' ? 'light' : 'dark';
  return (
    <button type="button" className="btn ghost icon" onClick={() => setTheme(next)} aria-label={`Switch to ${next} theme`}>
      {theme === 'dark' ? <Sun size={20} aria-hidden="true" /> : <Moon size={20} aria-hidden="true" />}
    </button>
  );
}

function navFor(user) {
  const items = [{ to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true }];
  if (can.sample(user)) items.push({ to: '/sample', label: 'Sample', icon: Camera });
  if (can.review(user)) items.push({ to: '/review', label: 'Review', icon: Stethoscope, badge: true });
  if (can.evaluate(user)) items.push({ to: '/evaluation', label: 'Evaluation', icon: FlaskConical });
  if (can.admin(user)) items.push({ to: '/maintenance', label: 'Maintenance', icon: Wrench });
  if (user.role === 'caretaker') items.push({ to: '/faqs', label: 'FAQs', icon: CircleHelp });
  return items;
}

function SystemChips({ system }) {
  if (!system) return null;
  const s = system.screener || {};
  const chips = [
    s.available ? { cls: 'ok', text: `Screening: ${s.name}` } : { cls: 'bad', text: 'Screening model unavailable' },
    { cls: system.segmentation?.startsWith('yolo') ? 'ok' : 'warn', text: `Outline: ${system.segmentation}` },
  ];
  return (
    <div className="syschips" aria-label="System status">
      {chips.map((c) => (
        <span key={c.text} className={`syschip ${c.cls}`}><span className="dot" aria-hidden="true" />{c.text}</span>
      ))}
    </div>
  );
}

export default function Shell() {
  const { user, system, loading, logout } = useAuth();
  const location = useLocation();
  const queue = useResource(user && can.review(user) ? '/api/review/queue' : null, { interval: 30000 });
  if (loading) return <div className="content"><Loading /></div>;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  const pending = queue.data ? queue.data.fish.length + queue.data.rounds.length : 0;
  const NAV = navFor(user);

  return (
    <>
      <a href="#main" className="skip-link">Skip to content</a>
      <div className="shell">
        <aside className="sidebar" aria-label="Main navigation">
          <Link to="/" className="brand">
            <span className="brand-mark"><FishMark /></span>
            <span>Tilapiers<small>Fish health · weight · harvest</small></span>
          </Link>
          <nav className="sidenav">
            {NAV.map(({ to, label, icon: Icon, end, badge }) => (
              <NavLink key={to} to={to} end={end}>
                <Icon size={19} aria-hidden="true" />
                {label}
                {badge && pending > 0 && <span className="nav-count" aria-label={`${pending} waiting`}>{pending}</span>}
              </NavLink>
            ))}
            <span className="sidenav-label">Help</span>
            {user.role !== 'caretaker' && (
              <NavLink to="/faqs"><CircleHelp size={19} aria-hidden="true" />FAQs</NavLink>
            )}
            <NavLink to="/about"><BookOpen size={19} aria-hidden="true" />About Us</NavLink>
          </nav>
          <div className="sidebar-foot">
            <Link to="/profile" className="user-chip">
              <UserRound size={18} aria-hidden="true" />
              <span>{user.full_name}<small>{ROLE_LABEL[user.role]}</small></span>
            </Link>
            <span className="subtle">
              <ClipboardCheck size={14} aria-hidden="true" style={{ verticalAlign: '-2px' }} /> Screening and
              decision support only: not a diagnosis, and not a harvest decision.
            </span>
          </div>
        </aside>

        <div className="main">
          {system?.demo && (
            <div className="demo-banner" role="note">
              <Info size={18} aria-hidden="true" />
              <span><strong>Demo mode.</strong> The two seeded ponds and their past rounds are example data, labeled
                “Demo data”. Photos you upload are processed for real.</span>
            </div>
          )}
          <header className="topbar">
            <Link to="/" className="brand brand-mobile" aria-label="Tilapiers home">
              <span className="brand-mark"><FishMark /></span>
              <span>Tilapiers</span>
            </Link>
            <span className="topbar-spacer" />
            <SystemChips system={system} />
            <ThemeToggle />
            <Link to="/profile" className="btn ghost icon topbar-user" aria-label={`Profile: ${user.full_name}`}>
              <UserRound size={20} aria-hidden="true" />
            </Link>
            <button type="button" className="btn ghost icon" onClick={logout} aria-label="Log out">
              <LogOut size={20} aria-hidden="true" />
            </button>
          </header>
          <main id="main" className="content" tabIndex={-1}>
            <Outlet />
          </main>
        </div>

        <nav className="bottomnav" aria-label="Main navigation">
          {NAV.slice(0, 5).map(({ to, label, icon: Icon, end, badge }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={22} aria-hidden="true" />
              <span>{label}</span>
              {badge && pending > 0 && <span className="nav-badge" aria-label={`${pending} waiting`}>{pending > 99 ? '99+' : pending}</span>}
            </NavLink>
          ))}
        </nav>
      </div>
    </>
  );
}

/** Wraps a page that only some roles may open. */
export function RoleGate({ allow, children }) {
  const { user } = useAuth();
  if (!allow(user)) return <Navigate to="/" replace />;
  return children;
}
