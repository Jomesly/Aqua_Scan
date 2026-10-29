import {
  CheckCircle2, CircleDashed, Clock, Database, Eye, FlaskConical, HelpCircle, ShieldAlert, ShieldCheck,
  Stethoscope, TrendingUp, Droplet, Eraser,
} from 'lucide-react';

const HEALTH = {
  Normal: { tone: 'good', Icon: ShieldCheck },
  Watch: { tone: 'moderate', Icon: Eye },
  'Refer to technician': { tone: 'critical', Icon: Stethoscope },
  'Not screened': { tone: 'unknown', Icon: CircleDashed },
  'Insufficient data': { tone: 'unknown', Icon: HelpCircle, label: 'No data' },
};

const READINESS = {
  Ready: { tone: 'good', Icon: CheckCircle2 },
  'Size reached - health review needed': { tone: 'moderate', Icon: ShieldAlert, label: 'Size reached · health review' },
  Approaching: { tone: 'accent', Icon: TrendingUp },
  'Not Ready': { tone: 'unknown', Icon: Clock },
  'Insufficient data': { tone: 'unknown', Icon: HelpCircle, label: 'No data' },
};

const CLASSES = {
  'No visible defect': { tone: 'good', Icon: ShieldCheck },
  'Skin erosion': { tone: 'critical', Icon: Eraser },
  'Red sores': { tone: 'critical', Icon: Droplet },
};

function Badge({ map, value, size, prefix, suffix }) {
  const spec = map[value] || { tone: 'unknown', Icon: HelpCircle };
  const { Icon } = spec;
  const text = spec.label || value || '—';
  return (
    <span className={`badge tone-${spec.tone} ${size === 'lg' ? 'lg' : ''}`}>
      <Icon size={size === 'lg' ? 18 : 15} aria-hidden="true" />
      {prefix ? <span className="sr-only">{prefix}: </span> : null}
      {text}
      {suffix ? <span className="badge-suffix">{suffix}</span> : null}
    </span>
  );
}

export const HealthBadge = (p) => <Badge map={HEALTH} prefix="Health" {...p} />;
export const ReadinessBadge = (p) => <Badge map={READINESS} prefix="Harvest readiness" {...p} />;

export function ClassBadge({ cls, conf, size }) {
  if (!cls) return <Badge map={HEALTH} value="Not screened" size={size} prefix="Screening" />;
  return <Badge map={CLASSES} value={cls} size={size} prefix="Screening"
    suffix={conf != null ? `${Math.round(conf * 100)}%` : null} />;
}

export function DemoTag() {
  return <span className="tag demo"><Database size={12} aria-hidden="true" />Demo data</span>;
}

export function ProvisionalTag({ children = 'Provisional' }) {
  return <span className="tag warn"><FlaskConical size={12} aria-hidden="true" />{children}</span>;
}

export const healthTone = (s) => (HEALTH[s] || HEALTH['Insufficient data']).tone;
export const readinessTone = (s) => (READINESS[s] || READINESS['Insufficient data']).tone;
