import { createContext, useContext, useEffect, useState } from 'react';
import { NavLink, Link, Outlet } from 'react-router-dom';
import {
  Bell, Camera, ClipboardCheck, FlaskConical, LayoutDashboard, Moon, Settings, Sun, Info,
} from 'lucide-react';
import { useResource } from '../lib/api';

const SystemCtx = createContext({ system: null, unread: 0, reloadSystem: () => {} });
export const useSystem = () => useContext(SystemCtx);

export function FishMark({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none">
      <path d="M2.5 12c2.6-4.3 7.6-5.6 11-2.6L17 7v10l-3.5-2.4c-3.4 3-8.4 1.7-11-2.6z" fill="currentColor" />
      <circle cx="6.6" cy="11.2" r="1" fill="var(--primary)" />
      <path d="M17 7l4.5-2v14L17 17" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function ThemeToggle() {
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

function SystemChips({ system }) {
  if (!system) return null;
  const sensor = system.sensor || {};
  let probe = { cls: 'bad', text: 'Probe: not connected' };
  if (sensor.mode === 'simulate') probe = { cls: 'warn', text: 'Probe: simulated' };
  else if (sensor.mode === 'off') probe = { cls: '', text: 'Probe: network ingest' };
  else if (sensor.probe_port) probe = { cls: 'ok', text: `Probe: ${sensor.probe_port}` };
  const det = system.detector?.is_stub ? { cls: 'warn', text: 'Detector: stub' } : { cls: 'ok', text: 'Detector: YOLO26' };
  const ch = system.notifications;
  const alerts = ch?.ready ? { cls: 'ok', text: `Alerts: ${ch.channel}` } : { cls: '', text: 'Alerts: dashboard only' };
  return (
    <div className="syschips" aria-label="System status">
      {[probe, det, alerts].map((c) => (
        <span key={c.text} className={`syschip ${c.cls}`}><span className="dot" aria-hidden="true" />{c.text}</span>
      ))}
    </div>
  );
}

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/sample', label: 'Sampling', icon: Camera },
  { to: '/alerts', label: 'Alerts', icon: Bell, badge: true },
  { to: '/evaluation', label: 'Evaluation', icon: FlaskConical },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Shell() {
  const { data: system, reload: reloadSystem } = useResource('/api/system', { interval: 15000 });
  const { data: notes, reload: reloadUnread } = useResource('/api/notifications?limit=200', { interval: 10000 });
  const unread = notes?.notifications?.filter((n) => !n.acknowledged).length || 0;

  return (
    <SystemCtx.Provider value={{ system, unread, reloadSystem, reloadUnread }}>
      <a href="#main" className="skip-link">Skip to content</a>
      <div className="shell">
        <aside className="sidebar" aria-label="Main navigation">
          <Link to="/" className="brand">
            <span className="brand-mark"><FishMark /></span>
            <span>Tilapiers<small>Pond monitoring</small></span>
          </Link>
          <nav className="sidenav">
            {NAV.map(({ to, label, icon: Icon, end, badge }) => (
              <NavLink key={to} to={to} end={end}>
                <Icon size={19} aria-hidden="true" />
                {label}
                {badge && unread > 0 && <span className="nav-count" aria-label={`${unread} unread`}>{unread}</span>}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-foot">
            <span className="subtle">
              <ClipboardCheck size={14} aria-hidden="true" style={{ verticalAlign: '-2px' }} /> Screening and decision support only.
              Health and readiness are rule-based assessments, not diagnoses or forecasts.
            </span>
          </div>
        </aside>

        <div className="main">
          {system?.demo && (
            <div className="demo-banner" role="note">
              <Info size={18} aria-hidden="true" />
              <span><strong>Demo mode.</strong> Ponds, readings and fish are seeded or simulated for presentation; they are labeled as demo data throughout.</span>
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
          </header>
          <main id="main" className="content" tabIndex={-1}>
            <Outlet />
          </main>
        </div>

        <nav className="bottomnav" aria-label="Main navigation">
          {NAV.map(({ to, label, icon: Icon, end, badge }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={22} aria-hidden="true" />
              <span>{label}</span>
              {badge && unread > 0 && <span className="nav-badge" aria-label={`${unread} unread`}>{unread > 99 ? '99+' : unread}</span>}
            </NavLink>
          ))}
        </nav>
      </div>
    </SystemCtx.Provider>
  );
}
