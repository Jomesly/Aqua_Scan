import {
  AlertTriangle, CheckCircle2, Clock, Eye, HelpCircle, OctagonAlert, ShieldAlert,
  ShieldCheck, Stethoscope, TrendingUp, WifiOff,
} from 'lucide-react';

const ENV = {
  Good: { tone: 'good', Icon: CheckCircle2 },
  Moderate: { tone: 'moderate', Icon: AlertTriangle },
  Critical: { tone: 'critical', Icon: OctagonAlert },
  Unknown: { tone: 'unknown', Icon: WifiOff, label: 'Probe offline' },
};

const HEALTH = {
  Normal: { tone: 'good', Icon: ShieldCheck },
  Watch: { tone: 'moderate', Icon: Eye },
  'Refer to technician': { tone: 'critical', Icon: Stethoscope },
  'Insufficient data': { tone: 'unknown', Icon: HelpCircle, label: 'No data' },
};

const READINESS = {
  Ready: { tone: 'good', Icon: CheckCircle2 },
  'Size reached - health review needed': { tone: 'moderate', Icon: ShieldAlert, label: 'Size reached · health review' },
  Approaching: { tone: 'accent', Icon: TrendingUp },
  'Not Ready': { tone: 'unknown', Icon: Clock },
  'Insufficient data': { tone: 'unknown', Icon: HelpCircle, label: 'No data' },
};

function Badge({ map, value, size, prefix }) {
  const spec = map[value] || { tone: 'unknown', Icon: HelpCircle };
  const { Icon } = spec;
  const text = spec.label || value || '—';
  return (
    <span className={`badge tone-${spec.tone} ${size === 'lg' ? 'lg' : ''}`}>
      <Icon size={size === 'lg' ? 18 : 15} aria-hidden="true" />
      {prefix ? <span className="sr-only">{prefix}: </span> : null}
      {text}
    </span>
  );
}

export const EnvBadge = (p) => <Badge map={ENV} prefix="Environment" {...p} />;
export const HealthBadge = (p) => <Badge map={HEALTH} prefix="Health" {...p} />;
export const ReadinessBadge = (p) => <Badge map={READINESS} prefix="Harvest readiness" {...p} />;

export const envTone = (state) => (ENV[state] || ENV.Unknown).tone;
export const healthTone = (s) => (HEALTH[s] || HEALTH['Insufficient data']).tone;
