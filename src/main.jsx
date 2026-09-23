import React from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  Bell,
  Camera,
  CheckCircle2,
  Clock3,
  Eye,
  Fish,
  History,
  Home,
  Radio,
  Settings,
  ShieldAlert,
  Smartphone,
  Waves,
  Zap,
} from 'lucide-react';
import './styles.css';

const alerts = [
  {
    id: 'TL-2406-019',
    time: '2026-06-13 09:42:18',
    shortTime: '09:42',
    species: 'Tilapia',
    confidence: 94,
    severity: 'Unsafe',
    count: 0,
    camera: 'Feeding Zone - Camera 01',
    condition: 'Unsafe gate - feeding withheld',
    note: 'DO 2.6 mg/L below 3 mg/L. SMS sent to caretaker registered number (thesis Table 1).',
  },
  {
    id: 'TL-2406-018',
    time: '2026-06-13 09:34:05',
    shortTime: '09:34',
    species: 'Pellets',
    confidence: 88,
    severity: 'Warning',
    count: 6,
    camera: 'Feeding Zone - Camera 03',
    condition: 'Low depletion - session stopped',
    note: 'R < 0.40. Remaining pellets logged as uneaten-feed alert.',
  },
  {
    id: 'TL-2406-017',
    time: '2026-06-13 09:21:44',
    shortTime: '09:21',
    species: 'Pellets',
    confidence: 91,
    severity: 'Normal',
    count: 4,
    camera: 'Feeding Zone - Camera 02',
    condition: 'High depletion - full increment',
    note: 'R ≥ 0.80. Next full increment (0.25 × D_ref) dispensed by actuator.',
  },
  {
    id: 'TL-2406-016',
    time: '2026-06-13 09:08:30',
    shortTime: '09:08',
    species: 'Tilapia',
    confidence: 86,
    severity: 'Normal',
    count: 5,
    camera: 'Feeding Zone - Camera 04',
    condition: 'Safe gate - feeding recommended',
    note: 'Temperature 27.4°C and DO 4.8 mg/L both inside Safe bands (Table 1).',
  },
];

const cameraTiles = [
  { name: 'Feeding Zone - Cam 01', species: 'Pellets', confidence: 94, fish: 12, condition: 'R high - continue', accent: 'from-sky-500/30' },
  { name: 'Feeding Zone - Cam 03', species: 'Pellets', confidence: 88, fish: 6, condition: 'R moderate - half dose', accent: 'from-cyan-500/25' },
  { name: 'Feeding Zone - Cam 02', species: 'Pellets', confidence: 91, fish: 4, condition: 'R low - uneaten feed', accent: 'from-emerald-500/25' },
  { name: 'Feeding Zone - Cam 04', species: 'Tilapia', confidence: 82, fish: 2, condition: 'gate Safe', accent: 'from-indigo-500/25' },
];

const waterSensors = [
  {
    name: 'Water Temperature',
    value: '27.4',
    unit: '°C',
    status: 'Safe',
    trend: 'Gate: 25°C ≤ T ≤ 31°C',
    note: 'thesis Table 1',
  },
  {
    name: 'Dissolved Oxygen',
    value: '4.8',
    unit: 'mg/L',
    status: 'Safe',
    trend: 'Gate: 3 ≤ DO ≤ 5 mg/L',
    note: 'checked first (BFAR-NCR)',
  },
];

const gateThresholds = {
  temp: { min: 25, max: 31, unit: '°C' },
  oxygen: { min: 3, max: 5, unit: 'mg/L' },
};

const feedingSession = {
  dRef: '100%',
  increment: '0.25 × D_ref',
  observationWindow: '5 min',
  dispensed: '37.5%',
  ceiling: 'session cap = D_ref',
  state: 'Safe - feeding permitted',
};

const depletionTiers = [
  { rate: 'R ≥ 0.80', label: 'High depletion', action: 'Continue full increment', tone: 'high' },
  { rate: '0.40 ≤ R < 0.80', label: 'Moderate depletion', action: 'Reduce: half increment', tone: 'mod' },
  { rate: 'R < 0.40', label: 'Low depletion', action: 'Stop + uneaten-feed alert', tone: 'low' },
];

const detectionChecks = [
  { label: 'Environmental gate', value: 'Safe', detail: 'Temp and DO both inside Table 1 bands', status: 'pass' },
  { label: 'Feeding-zone ROI', value: 'Clear', detail: 'Fixed camera, feeding-zone region only', status: 'pass' },
  { label: 'Pellet depletion (R)', value: '0.64', detail: 'Moderate → next half increment', status: 'warn' },
  { label: 'Model confidence', value: '82-94%', detail: 'Low-confidence reads held (fail-safe)', status: 'warn' },
];

const historyRecords = [
  {
    id: 'HIS-2406-033',
    time: '2026-06-14 07:28:42',
    species: 'Pellets',
    condition: 'Unsafe gate - feeding withheld + SMS',
    confidence: 95,
    camera: 'Feeding Zone - Cam 01',
    severity: 'Unsafe',
    water: { temp: '32.1 °C', ph: '7.0', oxygen: '2.6 mg/L' },
  },
  {
    id: 'HIS-2406-032',
    time: '2026-06-14 03:12:09',
    species: 'Pellets',
    condition: 'Low depletion - uneaten-feed log',
    confidence: 89,
    camera: 'Feeding Zone - Cam 03',
    severity: 'Warning',
    water: { temp: '27.8 °C', ph: '7.4', oxygen: '5.0 mg/L' },
  },
  {
    id: 'HIS-2406-031',
    time: '2026-06-13 22:44:51',
    species: 'Pellets',
    condition: 'High depletion - full increment',
    confidence: 92,
    camera: 'Feeding Zone - Cam 02',
    severity: 'Normal',
    water: { temp: '26.9 °C', ph: '7.3', oxygen: '6.2 mg/L' },
  },
  {
    id: 'HIS-2406-030',
    time: '2026-06-13 15:36:18',
    species: 'Pellets',
    condition: 'Moderate depletion - half increment',
    confidence: 87,
    camera: 'Feeding Zone - Cam 04',
    severity: 'Warning',
    water: { temp: '29.0 °C', ph: '7.1', oxygen: '4.2 mg/L' },
  },
  {
    id: 'HIS-2406-029',
    time: '2026-06-13 08:05:27',
    species: 'Tilapia',
    condition: 'Safe gate - session started',
    confidence: 91,
    camera: 'Feeding Zone - Cam 01',
    severity: 'Normal',
    water: { temp: '27.2 °C', ph: '7.5', oxygen: '5.5 mg/L' },
  },
  {
    id: 'HIS-2406-028',
    time: '2026-06-12 18:49:03',
    species: 'Waste',
    condition: 'Uneaten feed flagged in ROI',
    confidence: 93,
    camera: 'Feeding Zone - Cam 02',
    severity: 'Warning',
    water: { temp: '28.6 °C', ph: '6.8', oxygen: '4.8 mg/L' },
  },
];

const timeline = [22, 18, 15, 14, 17, 26, 42, 58, 64, 73, 68, 71, 79, 86, 82, 91, 96, 88, 76, 62, 54, 47, 39, 31];

const correlationData = [
  { hour: '00:00', detections: 18, oxygen: 4.9 },
  { hour: '01:00', detections: 16, oxygen: 4.8 },
  { hour: '02:00', detections: 14, oxygen: 4.7 },
  { hour: '03:00', detections: 17, oxygen: 4.6 },
  { hour: '04:00', detections: 21, oxygen: 4.5 },
  { hour: '05:00', detections: 24, oxygen: 4.3 },
  { hour: '06:00', detections: 28, oxygen: 4.0 },
  { hour: '07:00', detections: 34, oxygen: 3.7 },
  { hour: '08:00', detections: 45, oxygen: 3.4 },
  { hour: '09:00', detections: 72, oxygen: 2.8 },
  { hour: '10:00', detections: 68, oxygen: 3.2 },
  { hour: '11:00', detections: 54, oxygen: 3.6 },
];

function severityClass(severity) {
  if (severity === 'Critical' || severity === 'Unsafe') return 'bg-red-500/15 text-red-300 ring-red-400/40';
  if (severity === 'Warning') return 'bg-amber-400/15 text-amber-200 ring-amber-300/40';
  return 'bg-emerald-400/15 text-emerald-200 ring-emerald-300/40';
}

function mobileSeverityClass(severity) {
  if (severity === 'Critical' || severity === 'Unsafe') return 'bg-red-100 text-red-700';
  if (severity === 'Warning') return 'bg-amber-100 text-amber-700';
  return 'bg-emerald-100 text-emerald-700';
}

function dashboardSensorBadgeClass(status) {
  if (status === 'Unsafe' || status === 'Critical') return 'bg-red-500/15 text-red-200 ring-red-400/40';
  if (status === 'Warning') return 'bg-amber-400/15 text-amber-200 ring-amber-300/40';
  return 'bg-emerald-400/15 text-emerald-200 ring-emerald-300/40';
}

function openLiveDashboard() {
  window.open('http://127.0.0.1:8000/', '_blank', 'noopener,noreferrer');
}

function AquaLogo({ compact = false }) {
  return (
    <div className="flex items-center gap-3">
      <div className="grid size-11 place-items-center rounded-2xl bg-sky-500/15 ring-1 ring-sky-400/35">
        <Fish className="size-6 text-cyan-300" />
      </div>
      {!compact && (
        <div>
          <div className="text-xl font-semibold tracking-tight text-white">Tilapiers</div>
          <div className="text-xs uppercase tracking-[0.28em] text-slate-400">Pellet detection and feeding</div>
        </div>
      )}
    </div>
  );
}

function SimulatedFeed({ compact = false, tile }) {
  return (
    <div className={`relative overflow-hidden rounded-[1.7rem] border border-white/10 bg-slate-950 shadow-2xl ${compact ? 'min-h-44' : 'min-h-72'}`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${tile?.accent || 'from-sky-500/25'} via-slate-900 to-slate-950`} />
      <div className="absolute inset-0 opacity-35 [background-image:radial-gradient(circle_at_25%_30%,#67e8f9_0,transparent_28%),radial-gradient(circle_at_78%_65%,#0ea5e9_0,transparent_24%)]" />
      <div className="absolute inset-x-0 bottom-0 h-28 bg-[repeating-linear-gradient(170deg,transparent_0_16px,rgba(6,182,212,.16)_17px_19px)]" />
      <div className="absolute left-[19%] top-[32%] h-[30%] w-[46%] rounded-[45%] border-2 border-cyan-300 shadow-[0_0_28px_rgba(6,182,212,.35)]" />
      <div className="absolute left-[23%] top-[39%] h-5 w-20 rounded-full bg-cyan-200/70 blur-sm" />
      <div className="absolute left-[57%] top-[36%] h-[25%] w-[25%] rounded-[45%] border-2 border-sky-300" />
      <div className="absolute left-[18%] top-[25%] rounded-full bg-cyan-300 px-2.5 py-1 text-[11px] font-semibold text-slate-950 shadow-lg">
        {tile ? `${tile.species} ${tile.confidence}% - ${tile.condition}` : 'Pellets detected - 12 in ROI (94% confidence)'}
      </div>
      <div className="absolute right-4 top-4 flex items-center gap-2 rounded-full bg-slate-950/70 px-3 py-1.5 text-xs font-medium text-cyan-100 backdrop-blur">
        <span className="size-2 rounded-full bg-emerald-400 shadow-[0_0_12px_#22c55e]" /> Live
      </div>
      <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between rounded-2xl bg-slate-950/70 px-4 py-3 text-sm text-white backdrop-blur">
        <span>{tile?.name || 'Feeding Zone - Camera 01'}</span>
        <span className="text-cyan-200">YOLOv8n - {tile?.fish || 12} pellets</span>
      </div>
    </div>
  );
}

function MobileHome({ activeScreen = 'Home', onScreenChange }) {
  return (
    <section className="flex h-full flex-col bg-slate-50">
      <div className="bg-gradient-to-br from-sky-500 to-cyan-500 px-5 pb-7 pt-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-sky-100">Tilapiers Mobile</div>
            <h2 className="text-2xl font-semibold">Live camera feed</h2>
          </div>
          <div className="grid size-11 place-items-center rounded-full bg-white/18">
            <Camera className="size-5" />
          </div>
        </div>
      </div>
      <div className="-mt-4 flex-1 px-4 pb-3">
        <div className="relative">
          <SimulatedFeed />
          <div className="absolute -top-3 left-5 flex items-center gap-2 rounded-full bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-xl ring-1 ring-slate-200">
            <span className="size-2 rounded-full bg-emerald-500" /> AI active - 12 pellets detected
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <InfoPill icon={<Activity />} label="Env gate" value="Safe - Temp + DO" />
          <InfoPill icon={<Radio />} label="Live stream" value="MJPEG /stream" />
        </div>
        <MobileSensorStrip />
      </div>
      <MobileNav active={activeScreen} onSelect={onScreenChange} />
    </section>
  );
}

function MobileSensorStrip() {
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between px-1">
        <div className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">ESP32 sensors - live</div>
        <Waves className="size-4 text-sky-500" />
      </div>
      <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2">
        {waterSensors.map((sensor) => (
          <article key={sensor.name} className="min-w-[145px] rounded-2xl bg-white p-3 shadow-sm ring-1 ring-slate-200">
            <div className="text-xs font-medium text-slate-500">{sensor.name}</div>
            <div className="mt-2 flex items-baseline gap-1">
              <span className="text-2xl font-bold text-slate-950">{sensor.value}</span>
              {sensor.unit && <span className="text-xs font-semibold text-slate-500">{sensor.unit}</span>}
            </div>
            <span className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${mobileSeverityClass(sensor.status)}`}>
              {sensor.status}{sensor.note ? ` - ${sensor.note}` : ''}
            </span>
          </article>
        ))}
      </div>
    </div>
  );
}

function InfoPill({ icon, label, value }) {
  return (
    <div className="rounded-2xl bg-white p-3 shadow-sm ring-1 ring-slate-200">
      <div className="mb-2 text-sky-500 [&_svg]:size-4">{icon}</div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function MobileAlerts({ activeScreen = 'Alerts', onScreenChange }) {
  return (
    <section className="flex h-full flex-col bg-slate-50">
      <div className="px-5 pb-3 pt-6">
        <div className="text-sm font-medium text-sky-600">Firebase Cloud Messaging</div>
        <h2 className="text-2xl font-semibold text-slate-950">Feeding alerts</h2>
      </div>
      <div className="flex-1 space-y-3 overflow-hidden px-4">
        {alerts.slice(0, 3).map((alert) => (
          <article key={alert.id} className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs text-slate-500">{alert.time}</div>
                <div className="mt-1 text-lg font-semibold text-slate-950">{alert.species}</div>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${mobileSeverityClass(alert.severity)}`}>{alert.severity}</span>
            </div>
            <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
              <span>{alert.confidence}% confidence</span>
              <span>{alert.condition}</span>
            </div>
            <button className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-sky-500 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-500/20">
              <Eye className="size-4" /> View footage
            </button>
          </article>
        ))}
      </div>
      <MobileNav active={activeScreen} onSelect={onScreenChange} />
    </section>
  );
}

function MobileHistory({ activeScreen = 'History', onScreenChange }) {
  return (
    <section className="flex h-full flex-col bg-slate-50">
      <div className="px-5 pb-3 pt-6">
        <div className="text-sm font-medium text-sky-600">Detection archive</div>
        <h2 className="text-2xl font-semibold text-slate-950">History</h2>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 pb-3">
        {historyRecords.map((record) => (
          <article key={record.id} className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs text-slate-500">{record.time}</div>
                <div className="mt-1 text-lg font-semibold leading-tight text-slate-950">{record.species}</div>
                <div className="mt-1 text-sm leading-5 text-slate-600">{record.condition}</div>
              </div>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ${mobileSeverityClass(record.severity)}`}>{record.severity}</span>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3 text-sm text-slate-600">
              <span className="font-semibold text-slate-800">{record.confidence}% confidence</span>
              <span className="text-right text-xs">{record.camera}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <WaterChip label="Temp" value={record.water.temp} />
              <WaterChip label="DO" value={record.water.oxygen} />
            </div>
          </article>
        ))}
      </div>
      <MobileNav active={activeScreen} onSelect={onScreenChange} />
    </section>
  );
}

function WaterChip({ label, value }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700 ring-1 ring-slate-200">
      <span className="text-slate-500">{label}</span>
      {value}
    </span>
  );
}

function MobileSettings({ activeScreen = 'Settings', onScreenChange }) {
  return (
    <section className="flex h-full flex-col bg-slate-50">
      <div className="px-5 pb-3 pt-6">
        <div className="text-sm font-medium text-sky-600">Device controls</div>
        <h2 className="text-2xl font-semibold text-slate-950">Settings</h2>
      </div>
      <div className="flex-1 space-y-3 px-4">
        {[
          ['Camera sync', '4 feeds online'],
          ['ESP32 telemetry', 'Live sensor polling'],
          ['Alert delivery', 'Firebase notifications enabled'],
        ].map(([label, value]) => (
          <article key={label} className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <div className="text-sm font-semibold text-slate-950">{label}</div>
            <div className="mt-1 text-sm text-slate-500">{value}</div>
          </article>
        ))}
      </div>
      <MobileNav active={activeScreen} onSelect={onScreenChange} />
    </section>
  );
}

function MobileDetail({ onScreenChange }) {
  const alert = alerts[0];
  return (
    <section className="flex h-full flex-col bg-slate-950 text-white">
      <div className="px-5 pb-4 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-red-200">Notification detail</div>
            <h2 className="text-2xl font-semibold">Critical alert</h2>
          </div>
          <ShieldAlert className="size-8 text-red-300" />
        </div>
      </div>
      <div className="flex-1 px-4">
        <SimulatedFeed compact />
        <div className="mt-4 rounded-3xl bg-white p-4 text-slate-950">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-500">{alert.id}</div>
              <div className="text-xl font-bold">{alert.species} alert</div>
            </div>
            <span className={`rounded-full bg-red-100 px-3 py-1 text-xs font-bold text-red-700`}>{alert.severity}</span>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <Metric label="Fish count" value={alert.count} />
            <Metric label="Confidence" value={`${alert.confidence}%`} />
            <Metric label="Time" value={alert.shortTime} />
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-600">{alert.note} Snapshot recorded from {alert.camera} and queued for thesis demo review.</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 p-4">
        <button className="rounded-2xl bg-white px-4 py-3 text-sm font-bold text-slate-950">Mark as resolved</button>
        <button className="rounded-2xl bg-red-500 px-4 py-3 text-sm font-bold text-white">Escalate</button>
      </div>
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl bg-slate-100 px-2 py-3">
      <div className="text-lg font-bold text-slate-950">{value}</div>
      <div className="text-[11px] text-slate-500">{label}</div>
    </div>
  );
}

function MobileNav({ active, onSelect }) {
  const items = [
    ['Home', Home],
    ['Alerts', Bell],
    ['History', History],
    ['Settings', Settings],
  ];
  return (
    <nav className="grid grid-cols-4 border-t border-slate-200 bg-white px-2 py-2">
      {items.map(([label, Icon]) => (
        <button key={label} type="button" onClick={() => onSelect?.(label)} className={`flex flex-col items-center gap-1 rounded-2xl py-2 text-[11px] font-medium ${active === label ? 'bg-sky-50 text-sky-600' : 'text-slate-500'}`}>
          <Icon className="size-5" />
          {label}
        </button>
      ))}
    </nav>
  );
}

function PhoneFrame({ title, children }) {
  return (
    <div className="w-full max-w-[360px]">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
        <Smartphone className="size-4 text-cyan-300" /> {title}
      </div>
      <div className="h-[720px] overflow-hidden rounded-[2.5rem] border-8 border-slate-800 bg-white shadow-2xl shadow-sky-950/50 ring-1 ring-white/10">
        {children}
      </div>
    </div>
  );
}

function Dashboard() {
  return (
    <section className="min-w-[980px] flex-1 rounded-[2rem] border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-sky-950/40 backdrop-blur">
      <header className="flex items-center justify-between">
        <AquaLogo />
        <div className="flex items-center gap-3">
          <div className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-200">
            <span className="mr-2 inline-block size-2 rounded-full bg-emerald-400 shadow-[0_0_14px_#22c55e]" /> Gate Safe - feeding permitted
          </div>
          <button
            type="button"
            onClick={openLiveDashboard}
            className="inline-flex items-center gap-2 rounded-full border border-cyan-300/40 bg-cyan-400/15 px-4 py-2 text-sm font-bold text-cyan-100 transition hover:bg-cyan-400/25 hover:text-white"
            title="Open live camera dashboard with YOLOv8 stream"
          >
            <Camera className="size-4" />
            Open Live Camera
          </button>
        </div>
      </header>

      <div className="mt-6 grid grid-cols-4 gap-4">
        <StatCard icon={<Fish />} label="Pellet detections today" value="1,284" trend="Feeding-zone ROI only" />
        <StatCard icon={<AlertTriangle />} label="Unsafe / SMS alerts" value="7" trend="2 need review" warn />
        <StatCard icon={<Camera />} label="Camera feeds online" value="4 / 4" trend="Feeding-zone cameras" />
        <StatCard icon={<Clock3 />} label="Observation window" value="5 min" trend="Per increment (thesis)" />
      </div>

      <DashboardSensorRow />
      <EnvironmentGatePanel />
      <DepletionDecisionPanel />

      <div className="mt-6 grid grid-cols-[1fr_320px] gap-5">
        <main className="space-y-5">
          <div className="rounded-3xl border border-white/10 bg-slate-950/45 p-4">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Feeding-zone live grid (simulated)</h3>
                <p className="text-sm text-slate-400">YOLOv8 pellet counts in ROI - real camera opens via Live Camera button</p>
              </div>
              <button
                type="button"
                onClick={openLiveDashboard}
                className="inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1.5 text-xs font-bold text-cyan-100 hover:bg-cyan-300/20"
              >
                <Camera className="size-3.5" /> Stream
              </button>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {cameraTiles.map((tile) => (
                <SimulatedFeed key={tile.name} compact tile={tile} />
              ))}
            </div>
          </div>
          <TimelineChart />
          <CorrelationPanel />
          <DetectionReliabilityPanel />
        </main>
        <aside className="rounded-3xl border border-white/10 bg-slate-950/60 p-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">SMS / feeding alerts</h3>
              <p className="text-sm text-slate-400">Unsafe gate + uneaten-feed events</p>
            </div>
            <Bell className="size-5 text-cyan-300" />
          </div>
          <div className="max-h-[568px] space-y-3 overflow-y-auto pr-1">
            {[...alerts, ...alerts.slice(1, 4)].map((alert, index) => (
              <article key={`${alert.id}-${index}`} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-white">{alert.shortTime}</span>
                  <span className={`rounded-full px-2 py-1 text-[11px] font-bold ring-1 ${severityClass(alert.severity)}`}>{alert.severity}</span>
                </div>
                <div className="mt-2 text-sm text-slate-300">{alert.species} - {alert.confidence}% confidence</div>
                <div className="mt-1 text-xs text-slate-500">{alert.camera}</div>
                <div className="mt-1 text-xs leading-4 text-slate-500">{alert.condition}</div>
              </article>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

function EnvironmentGatePanel() {
  const safe = waterSensors.every((sensor) => sensor.status === 'Safe');

  return (
    <div className={`mt-6 rounded-3xl border p-4 ${safe ? 'border-emerald-300/25 bg-emerald-300/[0.06]' : 'border-red-300/30 bg-red-300/[0.08]'}`}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Environmental verification gate (Table 1)</h3>
          <p className="text-sm text-slate-400">
            Binary Safe/Unsafe - both temperature and dissolved oxygen must pass. pH / turbidity / ammonia are outside feeding-gate scope (thesis delimitations).
          </p>
        </div>
        <span className={`rounded-full px-4 py-2 text-sm font-bold ring-1 ${safe ? 'bg-emerald-400/15 text-emerald-200 ring-emerald-300/40' : 'bg-red-500/15 text-red-200 ring-red-400/40'}`}>
          {safe ? 'Safe - incremental feeding' : 'Unsafe - withhold + SMS'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <GateCard
          label="Temperature"
          value="27.4 °C"
          band={`${gateThresholds.temp.min}–${gateThresholds.temp.max} °C`}
          pass
        />
        <GateCard
          label="Dissolved oxygen"
          value="4.8 mg/L"
          band={`${gateThresholds.oxygen.min}–${gateThresholds.oxygen.max} mg/L`}
          pass
        />
        <GateCard
          label="Gate decision"
          value="Safe"
          band="Both parameters in band"
          pass
        />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs leading-5 text-slate-300">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <span className="font-bold text-emerald-200">Safe:</span> 25 °C ≤ T ≤ 31 °C and 3 ≤ DO ≤ 5 mg/L → feeding recommended; increments gated by depletion.
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <span className="font-bold text-red-200">Unsafe:</span> T &lt; 25 or T &gt; 31, or DO &lt; 3 mg/L → withhold feed; SMS to caretaker mobile.
        </div>
      </div>
    </div>
  );
}

function GateCard({ label, value, band, pass }) {
  return (
    <article className={`rounded-2xl border p-3 ${pass ? 'border-emerald-300/20 bg-emerald-300/[0.05]' : 'border-red-300/30 bg-red-300/[0.07]'}`}>
      <div className="text-xs text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${pass ? 'text-emerald-100' : 'text-red-100'}`}>{value}</div>
      <div className="mt-2 text-[11px] text-slate-500">{band}</div>
    </article>
  );
}

function DepletionDecisionPanel() {
  const toneClass = {
    high: 'border-emerald-300/25 bg-emerald-300/[0.06]',
    mod: 'border-amber-300/25 bg-amber-300/[0.08]',
    low: 'border-red-300/30 bg-red-300/[0.08]',
  };

  return (
    <div className="mt-6 rounded-3xl border border-white/10 bg-slate-950/45 p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Depletion-responsive feeding session</h3>
          <p className="text-sm text-slate-400">R = (P0 − Pt) / P0 over the 5-minute observation window after each increment</p>
        </div>
        <div className="rounded-full border border-sky-300/25 bg-sky-300/10 px-3 py-1.5 text-xs font-bold text-sky-100">
          {feedingSession.state}
        </div>
      </div>

      <div className="mb-4 grid grid-cols-5 gap-3">
        <SessionStat label="Reference dose D_ref" value={feedingSession.dRef} detail="Calibrated at stocking" />
        <SessionStat label="Increment size" value={feedingSession.increment} detail="Fixed step" />
        <SessionStat label="Observation window" value={feedingSession.observationWindow} detail="Post-dispense" />
        <SessionStat label="Session progress" value={feedingSession.dispensed} detail={feedingSession.ceiling} />
        <SessionStat label="Current R" value="0.64" detail="Moderate - half next" warn />
      </div>

      <div className="grid grid-cols-3 gap-3">
        {depletionTiers.map((tier) => (
          <article key={tier.label} className={`rounded-2xl border p-3 ${toneClass[tier.tone]}`}>
            <div className="text-xs font-semibold text-slate-400">{tier.rate}</div>
            <div className="mt-1 text-base font-bold text-white">{tier.label}</div>
            <div className="mt-2 text-sm text-slate-300">{tier.action}</div>
          </article>
        ))}
      </div>

      <div className="mt-4 rounded-2xl border border-sky-300/20 bg-sky-300/[0.07] p-3 text-sm leading-6 text-sky-100">
        Actuator dispenses automatically after each decision. Session hard-stops at D_ref. Low-confidence detections are held (not fed into R); uneaten pellets after Low depletion are logged as a water-quality risk.
      </div>
    </div>
  );
}

function SessionStat({ label, value, detail, warn = false }) {
  return (
    <article className={`rounded-2xl border p-3 ${warn ? 'border-amber-300/30 bg-amber-300/[0.08]' : 'border-white/10 bg-white/[0.04]'}`}>
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className={`mt-1 text-lg font-bold ${warn ? 'text-amber-100' : 'text-white'}`}>{value}</div>
      <div className="mt-1 text-[11px] text-slate-500">{detail}</div>
    </article>
  );
}

function DashboardSensorRow() {
  return (
    <div className="mt-6 grid grid-cols-2 gap-4">
      {waterSensors.map((sensor) => {
        const isWarning = sensor.status === 'Warning';

        return (
          <article
            key={sensor.name}
            className={`rounded-3xl border p-4 ${
              isWarning
                ? 'border-amber-300/30 bg-amber-300/[0.08] shadow-[0_0_30px_rgba(251,191,36,.08)]'
                : 'border-white/10 bg-slate-950/45'
            }`}
          >
            <div className="mb-5 flex items-start justify-between gap-3">
              <div className={`grid size-11 place-items-center rounded-2xl ${isWarning ? 'bg-amber-400/15 text-amber-200' : 'bg-cyan-400/10 text-cyan-300'}`}>
                <Waves className="size-5" />
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${dashboardSensorBadgeClass(sensor.status)}`}>
                {sensor.status}{sensor.note ? ` - ${sensor.note}` : ''}
              </span>
            </div>
            <div className="text-sm text-slate-400">{sensor.name}</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">{sensor.value}</span>
              {sensor.unit && <span className="text-sm font-semibold text-slate-400">{sensor.unit}</span>}
            </div>
            <div className={`mt-3 text-xs font-medium ${isWarning ? 'text-amber-200' : 'text-emerald-200'}`}>{sensor.trend}</div>
          </article>
        );
      })}
    </div>
  );
}

function StatCard({ icon, label, value, trend, warn = false }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
      <div className={`mb-5 grid size-11 place-items-center rounded-2xl ${warn ? 'bg-red-500/15 text-red-300' : 'bg-sky-500/15 text-cyan-300'}`}>{React.cloneElement(icon, { className: 'size-5' })}</div>
      <div className="text-sm text-slate-400">{label}</div>
      <div className="mt-1 text-3xl font-bold text-white">{value}</div>
      <div className={`mt-2 text-xs ${warn ? 'text-red-200' : 'text-emerald-200'}`}>{trend}</div>
    </div>
  );
}

function TimelineChart() {
  const max = Math.max(...timeline);
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-950/45 p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Detection timeline</h3>
          <p className="text-sm text-slate-400">Last 24 hours - pellet detections per hour</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-300"><Activity className="size-4 text-cyan-300" /> Peak at 16:00</div>
      </div>
      <div className="flex h-48 items-end gap-2 rounded-2xl bg-slate-950/70 p-4">
        {timeline.map((value, index) => (
          <div key={index} className="group flex flex-1 flex-col items-center gap-2">
            <div className="w-full rounded-t-lg bg-gradient-to-t from-sky-500 to-cyan-300 shadow-[0_0_18px_rgba(14,165,233,.25)] transition group-hover:from-red-400" style={{ height: `${(value / max) * 145}px` }} />
            <div className="text-[10px] text-slate-500">{index % 3 === 0 ? `${index}:00` : ''}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CorrelationPanel() {
  const maxDetections = Math.max(...correlationData.map((point) => point.detections));
  const minOxygen = 2.8;
  const maxOxygen = 5.0;
  const chartWidth = 660;
  const chartHeight = 220;
  const paddingX = 34;
  const paddingY = 26;
  const plotWidth = chartWidth - paddingX * 2;
  const plotHeight = chartHeight - paddingY * 2;
  const linePoints = correlationData
    .map((point, index) => {
      const x = paddingX + (index / (correlationData.length - 1)) * plotWidth;
      const y = paddingY + ((maxOxygen - point.oxygen) / (maxOxygen - minOxygen)) * plotHeight;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div className="rounded-3xl border border-white/10 bg-slate-950/45 p-4">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Sensor-detection correlation</h3>
          <p className="text-sm text-slate-400">Supports thesis claim: water quality gates safe feeding decisions</p>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-300">
          <span className="inline-flex items-center gap-2"><span className="size-2 rounded-full bg-cyan-300" /> Detections</span>
          <span className="inline-flex items-center gap-2"><span className="h-0.5 w-5 rounded-full bg-amber-300" /> Dissolved oxygen</span>
        </div>
      </div>

      <div className="rounded-2xl bg-slate-950/70 p-4">
        <div className="relative h-[260px]">
          <div className="absolute left-0 top-2 text-[11px] font-semibold text-slate-500">Fish count</div>
          <div className="absolute right-0 top-2 text-[11px] font-semibold text-amber-200">DO mg/L</div>
          <div className="absolute left-16 right-12 top-9 bottom-9 flex items-end gap-2 border-b border-l border-white/10 pl-3">
            {correlationData.map((point) => (
              <div key={point.hour} className="group flex h-full flex-1 flex-col justify-end gap-2">
                <div
                  className="w-full rounded-t-lg bg-gradient-to-t from-sky-500 to-cyan-300 shadow-[0_0_18px_rgba(14,165,233,.22)] transition group-hover:from-amber-300"
                  style={{ height: `${(point.detections / maxDetections) * 168}px` }}
                />
                <div className="text-center text-[10px] text-slate-500">{point.hour.replace(':00', '')}</div>
              </div>
            ))}
          </div>
          <svg className="pointer-events-none absolute left-16 right-12 top-9 bottom-9 h-[190px] w-[calc(100%-7rem)] overflow-visible" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none">
            <polyline points={linePoints} fill="none" stroke="#fbbf24" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
            {correlationData.map((point, index) => {
              const x = paddingX + (index / (correlationData.length - 1)) * plotWidth;
              const y = paddingY + ((maxOxygen - point.oxygen) / (maxOxygen - minOxygen)) * plotHeight;

              return <circle key={point.hour} cx={x} cy={y} r="5" fill="#fde68a" stroke="#0f172a" strokeWidth="2" />;
            })}
          </svg>
          <div className="absolute right-5 top-20 max-w-[280px] rounded-2xl border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-xs font-medium leading-5 text-amber-100">
            DO drop at 09:00 correlates with reduced pellet activity - feeding withheld
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <InsightCard text="Low DO detected → feeding withheld and SMS alert sent" tone="warning" />
        <InsightCard text="Temp and DO in Safe bands → feeding recommended" />
        <InsightCard text="Temperature rise at 14:00 → reduced depletion observed" tone="notice" />
      </div>
    </div>
  );
}

function InsightCard({ text, tone = 'normal' }) {
  const toneClass = tone === 'warning'
    ? 'border-amber-300/25 bg-amber-300/[0.08] text-amber-100'
    : tone === 'notice'
      ? 'border-sky-300/20 bg-sky-300/[0.07] text-sky-100'
      : 'border-white/10 bg-white/[0.04] text-slate-200';

  return (
    <div className={`rounded-2xl border p-3 text-sm font-medium leading-5 ${toneClass}`}>
      {text}
    </div>
  );
}

function DetectionReliabilityPanel() {
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-950/45 p-4">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Detection reliability scan</h3>
          <p className="text-sm text-slate-400">Use this when YOLOv8 pellet confidence drops or counts look unstable.</p>
        </div>
        <div className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 text-xs font-bold text-cyan-100">Demo QA checklist</div>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {detectionChecks.map((check) => {
          const isPass = check.status === 'pass';

          return (
            <article key={check.label} className={`rounded-2xl border p-3 ${isPass ? 'border-emerald-300/20 bg-emerald-300/[0.06]' : 'border-amber-300/25 bg-amber-300/[0.08]'}`}>
              <div className="mb-3 flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-white">{check.label}</span>
                {isPass ? <CheckCircle2 className="size-4 text-emerald-300" /> : <AlertTriangle className="size-4 text-amber-300" />}
              </div>
              <div className={`text-lg font-bold ${isPass ? 'text-emerald-200' : 'text-amber-200'}`}>{check.value}</div>
              <p className="mt-2 text-xs leading-5 text-slate-400">{check.detail}</p>
            </article>
          );
        })}
      </div>
        <div className="mt-4 rounded-2xl border border-sky-300/20 bg-sky-300/[0.07] p-4 text-sm leading-6 text-sky-100">
          Recommended fixes: train on feeding-zone videos, include empty-water negatives, keep the active classes as Tilapia / pellets / waste, hold low-confidence frames instead of feeding them into R, and maintain a confidence threshold around 0.50-0.65 for demos.
        </div>
    </div>
  );
}

function MobileAppScreen({ activeScreen, onScreenChange }) {
  if (activeScreen === 'Alerts') {
    return <MobileAlerts activeScreen={activeScreen} onScreenChange={onScreenChange} />;
  }

  if (activeScreen === 'History') {
    return <MobileHistory activeScreen={activeScreen} onScreenChange={onScreenChange} />;
  }

  if (activeScreen === 'Settings') {
    return <MobileSettings activeScreen={activeScreen} onScreenChange={onScreenChange} />;
  }

  return <MobileHome activeScreen={activeScreen} onScreenChange={onScreenChange} />;
}

function App() {
  const [activeScreen, setActiveScreen] = React.useState('Home');
  const activeTitle = activeScreen === 'Home' ? 'Screen 1 - Live camera feed' : `Screen 1 - ${activeScreen}`;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,.28),transparent_34%),linear-gradient(135deg,#020617,#0f172a_48%,#062134)] px-6 py-8 text-slate-100">
      <div className="mx-auto max-w-[1800px]">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-100">
              <Zap className="size-4 text-cyan-300" /> Parallel and distributed computing prototype
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-white md:text-6xl">Tilapiers monitoring system</h1>
            <p className="mt-3 max-w-3xl text-slate-300">Demo aligned to the thesis scope: YOLOv8 feed-pellet detection in the feeding zone, temperature and dissolved-oxygen safety gate, depletion-responsive feeding, SMS alerts, historical logs, and sensor-detection correlation.</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm text-slate-300">
            <div className="font-semibold text-white">Future integration notes</div>
            <div>YOLOv10 target - ESP32 water quality sensors - FCM escalation</div>
          </div>
        </div>

        <div className="flex flex-col gap-8 2xl:flex-row">
          <div className="grid gap-5 lg:grid-cols-3 2xl:grid-cols-1">
            <PhoneFrame title={activeTitle}>
              <MobileAppScreen activeScreen={activeScreen} onScreenChange={setActiveScreen} />
            </PhoneFrame>
            <PhoneFrame title="Screen 2 - Alerts"><MobileAlerts onScreenChange={setActiveScreen} /></PhoneFrame>
            <PhoneFrame title="Screen 3 - Notification detail"><MobileDetail onScreenChange={setActiveScreen} /></PhoneFrame>
          </div>
          <Dashboard />
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
