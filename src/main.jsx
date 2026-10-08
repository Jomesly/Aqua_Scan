import React from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  Bell,
  Camera,
  CheckCircle2,
  Clock3,
  Fish,
  History,
  Settings,
  ShieldAlert,
  Waves,
} from 'lucide-react';
import './styles.css';
import { api, useTelemetry, useNow } from './api';

// Paper constants. Mirrors tilapiers/paper_config.py - the backend is the
// authority at runtime, these are only the static thresholds shown in labels.
const TEMP_BAND = { min: 25, max: 31, unit: '°C' };
const DO_BAND = { min: 5, unit: 'mg/L' };
const OBSERVATION_WINDOW = '5 min';

const DEPLETION_TIERS = [
  { rate: 'R ≥ 0.80', label: 'High depletion', action: 'Continue: next full increment', tone: 'high' },
  { rate: '0.40 ≤ R < 0.80', label: 'Moderate depletion', action: 'Reduce: half increment', tone: 'mod' },
  { rate: 'R < 0.40', label: 'Low depletion', action: 'Stop + uneaten-feed alert', tone: 'low' },
];

const SESSION_STATUS = {
  running: { label: 'Session running', tone: 'live' },
  completed: { label: 'Completed', tone: 'ok' },
  low_depletion_stop: { label: 'Ended: low-depletion stop', tone: 'low' },
  session_cap_reached: { label: 'Ended: session cap reached', tone: 'ok' },
  gate_halt: { label: 'Ended: gate halt', tone: 'bad' },
  fail_safe: { label: 'Ended: fail-safe - no feeding action', tone: 'bad' },
};

const CLASSIFICATION_TONE = {
  High: 'border-emerald-300/25 bg-emerald-300/[0.07] text-emerald-100',
  Moderate: 'border-amber-300/25 bg-amber-300/[0.09] text-amber-100',
  Low: 'border-red-300/30 bg-red-300/[0.09] text-red-100',
};

const SEVERITY_CLASS = {
  critical: 'bg-red-500/15 text-red-300 ring-red-400/40',
  warning: 'bg-amber-400/15 text-amber-200 ring-amber-300/40',
  info: 'bg-emerald-400/15 text-emerald-200 ring-emerald-300/40',
};

const KIND_LABEL = {
  unsafe_env: 'Unsafe environment',
  uneaten_feed: 'Uneaten feed',
  fail_safe: 'Fail-safe',
  low_confidence: 'Low confidence',
  rapid_depletion: 'Rapid depletion',
  maintenance: 'Maintenance',
};

const FLAG_LABEL = {
  p0_zero: 'P0 = 0 - no classification',
  low_confidence: 'Low confidence - held',
  rapid_depletion: 'Rapid depletion - review',
};

const DEFERRED_MODULES = [
  'Authentication and role-based access',
  'Profile management (add / archive staff, assign admin)',
  'Backup and restore',
  'FAQ',
  'About us',
  'WebSocket / MQTT transport (polling used for now)',
];

function pad(value) {
  return String(value).padStart(2, '0');
}

function fmtDateTime(ms) {
  if (!ms) return '—';
  const d = new Date(ms);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function fmtTime(ms) {
  if (!ms) return '—';
  const d = new Date(ms);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fmtCountdown(ms) {
  if (ms == null) return '—';
  if (ms <= 0) return 'now';
  const total = Math.floor(ms / 1000);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours > 0) return `${hours}h ${pad(minutes)}m`;
  if (minutes > 0) return `${minutes}m ${pad(seconds)}s`;
  return `${seconds}s`;
}

function fmtRate(rate) {
  return rate == null ? '—' : rate.toFixed(2);
}

function severityClass(severity) {
  return SEVERITY_CLASS[severity] || SEVERITY_CLASS.info;
}

function alertSeverityLabel(severity) {
  if (severity === 'critical') return 'Unsafe';
  if (severity === 'warning') return 'Warning';
  return 'Info';
}

function gateStatusClass(pass) {
  return pass
    ? 'bg-emerald-400/15 text-emerald-200 ring-emerald-300/40'
    : 'bg-red-500/15 text-red-200 ring-red-400/40';
}

function openLiveDashboard() {
  api.openLiveDashboard();
}

function SimulatedBadge() {
  return (
    <span className="rounded-full bg-sky-400/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-sky-200 ring-1 ring-sky-300/40">
      Simulated
    </span>
  );
}

function SeedBadge() {
  return (
    <span className="rounded-full bg-slate-400/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-300 ring-1 ring-slate-300/30">
      Seed
    </span>
  );
}

function TestBadge() {
  return (
    <span className="rounded-full bg-violet-400/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-violet-200 ring-1 ring-violet-300/40">
      Test trigger
    </span>
  );
}

function AquaLogo() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid size-11 place-items-center rounded-2xl bg-sky-500/15 ring-1 ring-sky-400/35">
        <Fish className="size-6 text-cyan-300" />
      </div>
      <div>
        <div className="text-xl font-semibold tracking-tight text-white">Tilapiers</div>
        <div className="text-xs uppercase tracking-[0.28em] text-slate-400">Pellet detection and feeding</div>
      </div>
    </div>
  );
}

function LiveCameraTile({ status, pellets, total }) {
  const on = status?.camera_enabled !== false && !!status?.status;
  const confidence = status?.avg_confidence != null
    ? Math.round(status.avg_confidence * 100)
    : null;

  return (
    <div className="relative min-h-44 overflow-hidden rounded-[1.7rem] border border-white/10 bg-slate-950 shadow-2xl">
      <div className="absolute inset-0 bg-gradient-to-br from-sky-500/25 via-slate-900 to-slate-950" />
      <div className="absolute inset-0 opacity-35 [background-image:radial-gradient(circle_at_25%_30%,#67e8f9_0,transparent_28%),radial-gradient(circle_at_78%_65%,#0ea5e9_0,transparent_24%)]" />
      <div className="absolute inset-x-0 bottom-0 h-28 bg-[repeating-linear-gradient(170deg,transparent_0_16px,rgba(6,182,212,.16)_17px_19px)]" />
      <div className="absolute left-[19%] top-[32%] h-[30%] w-[46%] rounded-[45%] border-2 border-cyan-300 shadow-[0_0_28px_rgba(6,182,212,.35)]" />
      <div className="absolute left-[23%] top-[39%] h-5 w-20 rounded-full bg-cyan-200/70 blur-sm" />
      <div className="absolute left-[57%] top-[36%] h-[25%] w-[25%] rounded-[45%] border-2 border-sky-300" />
      <div className="absolute left-[18%] top-[25%] rounded-full bg-cyan-300 px-2.5 py-1 text-[11px] font-semibold text-slate-950 shadow-lg">
        {on
          ? `${pellets} pellets${confidence != null ? ` - ${confidence}% avg confidence` : ''}`
          : 'Camera off - no pellet count'}
      </div>
      <div className="absolute right-4 top-4 flex items-center gap-2 rounded-full bg-slate-950/70 px-3 py-1.5 text-xs font-medium text-cyan-100 backdrop-blur">
        <span className={`size-2 rounded-full ${on ? 'bg-emerald-400 shadow-[0_0_14px_#22c55e]' : 'bg-slate-500'}`} />
        {on ? 'Live' : 'Off'}
      </div>
      <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between rounded-2xl bg-slate-950/70 px-4 py-3 text-sm text-white backdrop-blur">
        <span>{status?.camera_label || 'Camera'}</span>
        <span className="text-cyan-200">YOLOv8 - {pellets} counted / {total} detected</span>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, sub, warn = false, badge = null }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
      <div className="mb-5 flex items-start justify-between">
        <div className={`grid size-11 place-items-center rounded-2xl ${warn ? 'bg-red-500/15 text-red-300' : 'bg-sky-500/15 text-cyan-300'}`}>
          {React.cloneElement(icon, { className: 'size-5' })}
        </div>
        {badge}
      </div>
      <div className="text-sm text-slate-400">{label}</div>
      <div className="mt-1 text-3xl font-bold text-white">{value}</div>
      <div className={`mt-2 text-xs ${warn ? 'text-red-200' : 'text-emerald-200'}`}>{sub}</div>
    </div>
  );
}

function GateCard({ label, value, band, pass, note, badge = null }) {
  return (
    <article className={`rounded-2xl border p-3 ${pass ? 'border-emerald-300/20 bg-emerald-300/[0.05]' : 'border-red-300/30 bg-red-300/[0.07]'}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs text-slate-400">{label}</div>
        {badge}
      </div>
      <div className={`mt-1 text-2xl font-bold ${pass ? 'text-emerald-100' : 'text-red-100'}`}>{value}</div>
      <div className="mt-2 text-[11px] text-slate-500">{band}</div>
      {note && <div className="mt-1 text-[11px] text-slate-400">{note}</div>}
    </article>
  );
}

function SectionHeader({ icon, title, subtitle, right = null }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-cyan-400/10 text-cyan-300">
          {React.cloneElement(icon, { className: 'size-5' })}
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="text-sm text-slate-400">{subtitle}</p>
        </div>
      </div>
      {right}
    </div>
  );
}

function EnvironmentGatePanel({ environment, schedule }) {
  const env = environment || {};
  const thresholds = env.thresholds || { temp_min_c: TEMP_BAND.min, temp_max_c: TEMP_BAND.max, do_min_mg: DO_BAND.min };
  const safe = env.gate_state === 'Safe';
  const tempPass = env.temperature_c != null
    && env.temperature_c >= thresholds.temp_min_c
    && env.temperature_c <= thresholds.temp_max_c;
  const doPass = env.dissolved_oxygen_mg != null
    && env.dissolved_oxygen_mg >= thresholds.do_min_mg;
  const failing = env.failing || [];
  const smsLog = env.sms_log || [];

  return (
    <section className={`mt-6 rounded-3xl border p-5 ${safe ? 'border-emerald-300/25 bg-emerald-300/[0.06]' : 'border-red-300/30 bg-red-300/[0.08]'}`}>
      <SectionHeader
        icon={<ShieldAlert />}
        title="Environmental verification gate (Table 2)"
        subtitle="Binary Safe/Unsafe. Both temperature and dissolved oxygen must pass; pH, turbidity and ammonia are outside the feeding-gate scope (thesis delimitations)."
        right={
          <div className="flex flex-col items-end gap-2">
            <span className={`rounded-full px-4 py-2 text-sm font-bold ring-1 ${gateStatusClass(safe)}`}>
              {safe ? 'Safe - incremental feeding' : 'Unsafe - withhold feed + SMS'}
            </span>
            {env.simulated && <SimulatedBadge />}
          </div>
        }
      />

      {!safe && failing.length > 0 && (
        <div className="mb-4 rounded-2xl border border-red-300/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-100">
          Failing parameter: {failing.join(' and ')} outside the Table 2 band.
        </div>
      )}
      {!env.available && (
        <div className="mb-4 rounded-2xl border border-red-300/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
          No water-quality reading available - treated as Unsafe, no feeding action.
        </div>
      )}

      <div className="grid grid-cols-3 gap-3">
        <GateCard
          label="Temperature"
          value={env.temperature_c == null ? '—' : `${env.temperature_c} °C`}
          band={`${thresholds.temp_min_c}–${thresholds.temp_max_c} °C`}
          pass={tempPass && env.valid !== false}
          badge={env.simulated ? <SimulatedBadge /> : null}
          note={env.time ? `Last reading ${env.time}` : null}
        />
        <GateCard
          label="Dissolved oxygen"
          value={env.dissolved_oxygen_mg == null ? '—' : `${env.dissolved_oxygen_mg} mg/L`}
          band={`≥ ${thresholds.do_min_mg} mg/L (no upper bound)`}
          pass={doPass && env.valid !== false}
          badge={env.simulated ? <SimulatedBadge /> : null}
          note={env.valid === false ? 'Invalid reading - feeding withheld' : null}
        />
        <GateCard
          label="Gate decision"
          value={safe ? 'Safe' : 'Unsafe'}
          band={safe ? 'Both parameters in band' : `Fails: ${failing.join(', ') || 'reading unavailable'}`}
          pass={safe}
          note="Re-checked immediately before every increment"
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs leading-5 text-slate-300">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <span className="font-bold text-emerald-200">Safe:</span> 25 °C ≤ T ≤ 31 °C and DO ≥ 5 mg/L → feeding permitted; each increment is gated by a fresh check.
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <span className="font-bold text-red-200">Unsafe:</span> T &lt; 25 °C or T &gt; 31 °C, or DO &lt; 5 mg/L → withhold feed; SMS to the caretaker's registered mobile.
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs leading-5 text-slate-300">
        <div className="rounded-2xl border border-sky-300/20 bg-sky-300/[0.07] p-3">
          <div className="mb-1 font-semibold text-sky-100">Pre-feed evaluation (1 h before each session)</div>
          {schedule ? (
            <>
              <div>Next session: <span className="font-semibold text-white">{schedule.next_session_fmt || '—'}</span></div>
              <div>Pre-feed check: <span className="font-semibold text-white">{schedule.prefeed_fmt || '—'}</span></div>
              <div>Result: <span className={`font-semibold ${schedule.prefeed_gate_state === 'Safe' ? 'text-emerald-200' : 'text-amber-200'}`}>{schedule.prefeed_result || 'Pending'}</span></div>
            </>
          ) : (
            <div>Schedule unavailable</div>
          )}
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <div className="mb-1 font-semibold text-white">SMS log (status and times)</div>
          {smsLog.length === 0 && <div className="text-slate-500">No SMS sent yet</div>}
          <div className="space-y-1">
            {smsLog.slice(0, 4).map((entry) => (
              <div key={entry.id} className="flex flex-wrap items-center justify-between gap-x-3">
                <span className="text-slate-400">{KIND_LABEL[entry.kind] || entry.kind}</span>
                <span className="text-emerald-200">{entry.sms_status || '—'}</span>
                <span className="text-slate-500">sent {entry.sms_sent_at || '—'}</span>
                <span className="text-slate-500">delivered {entry.sms_delivered_at || '—'}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function FeedingSessionPanel({ feeding, now, admin, onTestSession, testing, notice }) {
  const session = feeding?.session;
  const increments = feeding?.increments || [];
  const dRef = feeding?.d_ref_g || 0;
  const incrementSize = feeding?.increment_g || 0;
  const total = session?.total_dispensed_g || 0;
  const progress = dRef > 0 ? Math.min(100, (total / dRef) * 100) : 0;
  const schedule = feeding?.schedule;
  const current = increments[increments.length - 1];
  const lastIncrementHalf = current && current.size_g < incrementSize;
  const lastSession = feeding?.last_session;
  const lastIncrements = feeding?.last_increments || [];
  const activeSession = session || lastSession;
  const activeIncrements = session ? increments : lastIncrements;
  const status = activeSession
    ? (SESSION_STATUS[activeSession.status] || { label: activeSession.status, tone: 'ok' })
    : null;

  return (
    <section className="mt-6 rounded-3xl border border-white/10 bg-slate-950/45 p-5">
      <SectionHeader
        icon={<Clock3 />}
        title="Depletion-responsive feeding session"
        subtitle={`R = (P0 − Pt) / P0 over a strict ${OBSERVATION_WINDOW} observation window after each increment, against visible pellet depletion.`}
        right={
          <div className="flex flex-col items-end gap-2">
            <span className={`rounded-full px-3 py-1.5 text-xs font-bold ring-1 ${
              session
                ? 'bg-sky-400/15 text-sky-100 ring-sky-300/40'
                : 'bg-white/10 text-slate-200 ring-white/20'
            }`}>
              {session ? 'Session running' : status ? status.label : 'No session running'}
            </span>
            {session?.source === 'seed' && <SeedBadge />}
            {session?.source === 'test' && <TestBadge />}
          </div>
        }
      />

      {status?.tone === 'bad' && (
        <div className="mb-4 rounded-2xl border border-red-300/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-100">
          {status.label} - the system withheld all further feeding.
        </div>
      )}

      <div className="mb-4 grid grid-cols-5 gap-3">
        <SessionStat label="Reference dose D_ref" value={`${dRef.toFixed(2)} g`} detail="Hard session ceiling" />
        <SessionStat label="Increment size" value={`${incrementSize.toFixed(3)} g`} detail="0.25 × D_ref" />
        <SessionStat label="Next increment" value={lastIncrementHalf ? 'Half' : 'Full'} detail={lastIncrementHalf ? '0.5 × increment (Reduce Feed)' : '1 × increment'} warn={lastIncrementHalf} />
        <SessionStat label="Dispensed" value={`${total.toFixed(3)} g`} detail={`of ${dRef.toFixed(2)} g`} />
        <SessionStat
          label="Current R"
          value={fmtRate(current?.depletion_rate)}
          detail={current?.classification ? `${current.classification} - ${current.action}` : 'no classification'}
          warn={current?.classification === 'Low' || current?.classification === 'Moderate'}
        />
      </div>

      <div className="mb-4">
        <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
          <span>Session progress against D_ref</span>
          <span>{progress.toFixed(1)}% · ceiling = D_ref</span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-white/[0.06]">
          <div
            className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-3 text-xs text-slate-400">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <div className="mb-1 font-semibold text-white">Next session</div>
          <div className="text-lg font-bold text-white">
            {schedule?.next_session_at ? fmtCountdown(schedule.next_session_at - now) : '—'}
          </div>
          <div>{schedule?.next_session_fmt || 'no schedule'}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <div className="mb-1 font-semibold text-white">Pre-feed evaluation</div>
          <div className="font-bold text-white">{schedule?.prefeed_result || 'Pending'}</div>
          <div>1 h before start · gate {schedule?.prefeed_gate_state || '—'}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <div className="mb-1 font-semibold text-white">Gate re-check</div>
          <div className="font-bold text-white">Before every increment</div>
          <div>{feeding?.observation_window_s || 300} s window · culture stage {feeding?.culture_stage || '—'}</div>
        </div>
      </div>

      <div className="mb-4 overflow-hidden rounded-2xl border border-white/10">
        <table className="w-full text-left text-xs">
          <thead className="bg-white/[0.05] text-slate-400">
            <tr>
              <th className="px-3 py-2 font-semibold">#</th>
              <th className="px-3 py-2 font-semibold">Time</th>
              <th className="px-3 py-2 font-semibold">Size</th>
              <th className="px-3 py-2 font-semibold">P0</th>
              <th className="px-3 py-2 font-semibold">Pt</th>
              <th className="px-3 py-2 font-semibold">R</th>
              <th className="px-3 py-2 font-semibold">Classification</th>
              <th className="px-3 py-2 font-semibold">Action</th>
              <th className="px-3 py-2 font-semibold">Flag</th>
              <th className="px-3 py-2 font-semibold">t_exec → t_decision</th>
              <th className="px-3 py-2 font-semibold">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {activeIncrements.length === 0 && (
              <tr>
                <td className="px-3 py-4 text-slate-500" colSpan={11}>
                  No increments recorded yet.
                </td>
              </tr>
            )}
            {activeIncrements.map((row, index) => (
              <tr key={row.id} className="border-t border-white/[0.06] text-slate-300">
                <td className="px-3 py-2">{index + 1}</td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtTime(row.ts)}</td>
                <td className="px-3 py-2">{row.size_g.toFixed(3)} g</td>
                <td className="px-3 py-2">
                  {row.p_start}
                  {row.p0_simulated && <SimulatedBadge />}
                </td>
                <td className="px-3 py-2">
                  {row.p_end}
                  {row.pt_simulated && <SimulatedBadge />}
                </td>
                <td className="px-3 py-2 font-semibold text-white">{fmtRate(row.depletion_rate)}</td>
                <td className="px-3 py-2">
                  {row.classification ? (
                    <span className={`rounded-full px-2 py-1 text-[11px] font-bold ${CLASSIFICATION_TONE[row.classification] || 'bg-white/10 text-white'}`}>
                      {row.classification}
                    </span>
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </td>
                <td className="px-3 py-2">{row.action || '—'}</td>
                <td className="px-3 py-2">
                  {row.flag ? (
                    <span className="text-amber-200">{FLAG_LABEL[row.flag] || row.flag}</span>
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </td>
                <td className="px-3 py-2 whitespace-nowrap text-slate-400">
                  {fmtTime(row.t_exec)} → {fmtTime(row.t_decision)}
                  {row.decision_ms != null && <span className="ml-1 text-slate-500">({row.decision_ms} ms)</span>}
                </td>
                <td className="px-3 py-2">
                  <div className="flex gap-2">
                    <EvidenceThumb src={row.evidence_p0} label="P0" />
                    <EvidenceThumb src={row.evidence_pt} label="Pt" />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {activeSession && (
        <div className="mb-4 grid grid-cols-4 gap-3 text-xs">
          <KV label="Session" value={`#${activeSession.id}`} />
          <KV label="Started" value={fmtDateTime(activeSession.started_at)} />
          <KV label="End reason" value={status?.label || activeSession.status} />
          <KV label="Increments / dispensed" value={`${activeSession.increments_dispensed} · ${activeSession.total_dispensed_g.toFixed(3)} g`} />
        </div>
      )}

      <div className="grid grid-cols-3 gap-3">
        {DEPLETION_TIERS.map((tier) => (
          <article
            key={tier.label}
            className={`rounded-2xl border p-3 ${
              tier.tone === 'high'
                ? 'border-emerald-300/25 bg-emerald-300/[0.06]'
                : tier.tone === 'mod'
                  ? 'border-amber-300/25 bg-amber-300/[0.08]'
                  : 'border-red-300/30 bg-red-300/[0.08]'
            }`}
          >
            <div className="text-xs font-semibold text-slate-400">{tier.rate}</div>
            <div className="mt-1 text-base font-bold text-white">{tier.label}</div>
            <div className="mt-2 text-sm text-slate-300">{tier.action}</div>
          </article>
        ))}
      </div>

      <div className="mt-4 rounded-2xl border border-sky-300/20 bg-sky-300/[0.07] p-3 text-sm leading-6 text-sky-100">
        The actuator dispenses automatically after each decision - no manual dispense or approval step exists.
        The session hard-stops at D_ref. A P0 of 0, a below-threshold confidence, an implausibly rapid depletion
        or a camera dropout all hold the previous state and take no feeding action.
      </div>

      {admin && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-2xl border border-violet-300/25 bg-violet-400/[0.07] p-3">
          <TestBadge />
          <span className="text-xs text-violet-100">
            Admin - runs the normal session loop at the true {feeding?.observation_window_s || 300} s window.
          </span>
          <button
            type="button"
            onClick={onTestSession}
            disabled={testing || Boolean(session)}
            className="ml-auto rounded-full border border-violet-300/40 bg-violet-400/15 px-4 py-2 text-xs font-bold text-violet-100 transition hover:bg-violet-400/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {testing ? 'Starting…' : 'Run test session now'}
          </button>
          {notice && <span className="w-full text-xs text-violet-100">{notice}</span>}
        </div>
      )}
    </section>
  );
}

function KV({ label, value }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-semibold text-white">{value}</div>
    </div>
  );
}

function EvidenceThumb({ src, label }) {
  if (!src) return <span className="text-slate-600">{label}: none</span>;
  return (
    <a href={src} target="_blank" rel="noreferrer" title={`${label} evidence frame`}>
      <img src={src} alt={`${label} evidence`} className="h-12 w-20 rounded-lg border border-white/15 object-cover transition hover:border-cyan-300/60" />
    </a>
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

function DetectionEvidencePanel({ status }) {
  const classCounts = status?.class_counts || {};
  const entries = Object.entries(classCounts);
  const pellets = status?.pellet_count ?? 0;
  const total = status?.count ?? 0;

  return (
    <section className="mt-6 rounded-3xl border border-white/10 bg-slate-950/45 p-5">
      <SectionHeader
        icon={<Camera />}
        title="Detection evidence"
        subtitle="YOLOv8 oriented bounding boxes inside the feeding-zone ROI. Only feed pellets are counted for the depletion decision."
        right={
          <button
            type="button"
            onClick={openLiveDashboard}
            className="inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1.5 text-xs font-bold text-cyan-100 hover:bg-cyan-300/20"
          >
            <Camera className="size-3.5" /> Open live camera
          </button>
        }
      />

      <div className="grid grid-cols-4 gap-4">
        <StatCard icon={<Fish />} label="Pellets in feeding zone" value={pellets} sub="Counted - drives R" />
        <StatCard icon={<AlertTriangle />} label="Detected, not counted" value={total} sub={entries.length ? entries.map(([name, count]) => `${name}: ${count}`).join(' · ') : 'No detections yet'} />
        <StatCard icon={<Activity />} label="Rendered frame rate" value={`${(status?.render_fps ?? 0).toFixed(1)} fps`} sub={`Camera ${(status?.stream_fps ?? 0).toFixed(1)} fps · detection ${(status?.detect_fps ?? 0).toFixed(1)} fps`} />
        <StatCard icon={<CheckCircle2 />} label="Stream status" value={status?.camera_label || '—'} sub={status?.status || '—'} warn={status?.camera_enabled === false} />
      </div>

      <div className="mt-5 grid grid-cols-2 gap-4">
        <LiveCameraTile status={status} pellets={pellets} total={total} />
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Live stream, calibration and camera controls live on the caretaker dashboard at 127.0.0.1:8000.
      </p>
    </section>
  );
}

function AlertsPanel({ alerts }) {
  const rows = alerts?.alerts || [];

  return (
    <div className="rounded-3xl border border-white/10 bg-slate-950/60 p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">SMS / feeding alerts</h3>
          <p className="text-sm text-slate-400">Unsafe gate, uneaten feed and fail-safe events</p>
        </div>
        <Bell className="size-5 text-cyan-300" />
      </div>
      <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
        {rows.length === 0 && <div className="text-sm text-slate-500">No alerts yet.</div>}
        {rows.map((alert) => (
          <article key={alert.id} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-white">{fmtTime(alert.ts)}</span>
              <span className={`rounded-full px-2 py-1 text-[11px] font-bold ring-1 ${severityClass(alert.severity)}`}>
                {alertSeverityLabel(alert.severity)}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-2 text-sm text-slate-300">
              <span>{KIND_LABEL[alert.kind] || alert.kind}</span>
              {alert.sms && (
                <span className="rounded-full bg-sky-400/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sky-200 ring-1 ring-sky-300/40">
                  SMS {alert.sms_status || 'queued'}
                </span>
              )}
            </div>
            <div className="mt-1 text-xs leading-4 text-slate-500">{alert.message}</div>
            {alert.sms && (
              <div className="mt-1 text-[11px] text-slate-600">
                sent {alert.sms_sent_at || '—'} · delivered {alert.sms_delivered_at || '—'}
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}

function HistoryPanel({ history }) {
  const sessions = history?.sessions || [];

  return (
    <div className="rounded-3xl border border-white/10 bg-slate-950/45 p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Feeding history</h3>
          <p className="text-sm text-slate-400">Past sessions with their ending reason</p>
        </div>
        <History className="size-5 text-cyan-300" />
      </div>
      <div className="max-h-[560px] space-y-2 overflow-y-auto pr-1">
        {sessions.length === 0 && <div className="text-sm text-slate-500">No sessions recorded yet.</div>}
        {sessions.map((session) => {
          const status = SESSION_STATUS[session.status] || { label: session.status };
          return (
            <article key={session.id} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-white">Session #{session.id}</span>
                <span className="flex gap-1">
                  {session.seed && <SeedBadge />}
                  {session.test && <TestBadge />}
                </span>
              </div>
              <div className="mt-1 text-xs text-slate-400">{fmtDateTime(session.started_at)}</div>
              <div className="mt-1 text-xs text-slate-300">{status.label}</div>
              <div className="mt-1 text-xs text-slate-500">
                {session.increments_dispensed} increments · {session.total_dispensed_g.toFixed(3)} g of{' '}
                {session.d_ref_g.toFixed(2)} g · stage {session.culture_stage}
                {session.r_mean != null && ` · mean R ${fmtRate(session.r_mean)}`}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function SetupCard({ config, onSaved }) {
  const [abw, setAbw] = React.useState('');
  const [stocks, setStocks] = React.useState('');
  const [mobile, setMobile] = React.useState('');
  const [saving, setSaving] = React.useState(false);
  const [message, setMessage] = React.useState(null);

  React.useEffect(() => {
    if (!config) return;
    setAbw(String(config.abw_g ?? ''));
    setStocks(String(config.num_stocks ?? ''));
    setMobile(String(config.mobile_number ?? ''));
  }, [config]);

  if (!config) {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4 text-sm text-slate-400">
        Setup unavailable
      </div>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const next = await api.saveConfig({
        abw_g: Number(abw),
        num_stocks: Number(stocks),
        mobile_number: mobile,
      });
      setMessage({ ok: true, text: `Saved. Stage ${next.derived_stage}, D_ref ${next.d_ref_g.toFixed(2)} g.` });
      if (onSaved) onSaved(next);
    } catch (error) {
      setMessage({ ok: false, text: `Save failed: ${error.message}` });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Culture setup</h3>
          <p className="text-sm text-slate-400">Stocked biomass inputs the caretaker registers at stocking</p>
        </div>
        <Settings className="size-5 text-cyan-300" />
      </div>

      {config.out_of_band && (
        <div className="mb-4 rounded-2xl border border-amber-300/30 bg-amber-300/10 px-4 py-3 text-sm font-semibold text-amber-100">
          ABW {config.abw_g} g is outside every Table 1 band - holding the last valid stage ({config.culture_stage}).
        </div>
      )}

      <form onSubmit={submit} className="grid grid-cols-3 gap-3">
        <label className="block text-xs text-slate-400">
          Average body weight (g)
          <input
            className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
            type="number"
            step="0.1"
            min="0"
            value={abw}
            onChange={(event) => setAbw(event.target.value)}
            required
          />
        </label>
        <label className="block text-xs text-slate-400">
          Number of stocks
          <input
            className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
            type="number"
            step="1"
            min="1"
            value={stocks}
            onChange={(event) => setStocks(event.target.value)}
            required
          />
        </label>
        <label className="block text-xs text-slate-400">
          Registered mobile number
          <input
            className="mt-1 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
            type="text"
            value={mobile}
            onChange={(event) => setMobile(event.target.value)}
            required
          />
        </label>
        <div className="col-span-3 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-full border border-cyan-300/40 bg-cyan-400/15 px-4 py-2 text-sm font-bold text-cyan-100 transition hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save setup'}
          </button>
          {message && (
            <span className={`text-xs ${message.ok ? 'text-emerald-200' : 'text-red-200'}`}>{message.text}</span>
          )}
        </div>
      </form>

      <div className="mt-4 grid grid-cols-4 gap-3">
        <KV label="Culture stage (derived from ABW)" value={`${config.stage?.label} · Month ${config.stage?.month}`} />
        <KV label="Feeding rate / frequency" value={`${config.stage?.rate_pct}% · ${config.stage?.freq}× per day`} />
        <KV label="Reference dose D_ref" value={`${config.d_ref_g.toFixed(2)} g per session`} />
        <KV label="Increment (0.25 × D_ref)" value={`${config.increment_g.toFixed(3)} g`} />
      </div>

      <div className="mt-3 grid grid-cols-3 gap-3 text-xs text-slate-400">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <div className="font-semibold text-white">Feed</div>
          {config.stage?.feed}
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <div className="font-semibold text-white">Sessions per day</div>
          {config.stage?.sessions_per_day}
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
          <div className="font-semibold text-white">Weekly recalibration reminder</div>
          Re-sample ABW weekly and on restock, harvest or stage change.
          <div className="mt-1 text-slate-500">Last: {config.last_recalibrated_fmt || '—'}</div>
        </div>
      </div>
    </div>
  );
}

function NotImplementedNote() {
  return (
    <section className="mt-6 rounded-3xl border border-dashed border-white/15 bg-white/[0.03] p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-300" />
        <div>
          <h4 className="text-sm font-semibold text-white">Not yet implemented (deferred modules)</h4>
          <ul className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-slate-400">
            {DEFERRED_MODULES.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <span className="size-1.5 rounded-full bg-amber-300/70" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function AdminPanel({ config, onToggleSimulated, saving }) {
  return (
    <section className="mt-6 rounded-3xl border border-violet-300/25 bg-violet-400/[0.05] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Admin</h3>
          <p className="text-sm text-slate-400">
            Calibration sliders, camera source picker and the stop-camera button live on the caretaker dashboard.
            Label-only gate: authentication is a deferred module.
          </p>
        </div>
        <Settings className="size-5 text-violet-300" />
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-3">
        <SimulatedBadge />
        <span className="text-xs text-slate-300">
          Simulated feeding zone - fills in pellet counts when the camera sees none, so the depletion loop can be
          exercised. Turn it off to enforce the real P0 = 0 fail-safe.
        </span>
        <button
          type="button"
          onClick={onToggleSimulated}
          disabled={saving || !config}
          className="ml-auto rounded-full border border-violet-300/40 bg-violet-400/15 px-4 py-2 text-xs font-bold text-violet-100 transition hover:bg-violet-400/25 disabled:opacity-50"
        >
          {saving ? 'Saving…' : config?.simulate_pellets ? 'Turn off simulation' : 'Turn on simulation'}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 text-xs">
        <a
          href={api.exportUrl('increments')}
          className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-slate-200 transition hover:border-cyan-300/40"
        >
          <div className="font-semibold text-white">Export increments (CSV)</div>
          Size, P0, Pt, R, classification, action, flag, evidence
        </a>
        <a
          href={api.exportUrl('sensor_readings')}
          className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-slate-200 transition hover:border-cyan-300/40"
        >
          <div className="font-semibold text-white">Export sensor readings (CSV)</div>
          Temperature, dissolved oxygen, gate state, simulated flag
        </a>
        <a
          href={api.exportUrl('alerts')}
          className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-slate-200 transition hover:border-cyan-300/40"
        >
          <div className="font-semibold text-white">Export alerts (CSV)</div>
          Kind, severity, message, SMS status and times
        </a>
      </div>
      <button
        type="button"
        onClick={openLiveDashboard}
        className="mt-3 rounded-full border border-cyan-300/40 bg-cyan-400/15 px-4 py-2 text-xs font-bold text-cyan-100 hover:bg-cyan-400/25"
      >
        Open caretaker dashboard admin view
      </button>
    </section>
  );
}

function Dashboard({ state, now, admin, setAdmin, onTestSession, testing, notice, onToggleSimulated, savingConfig }) {
  const { environment, feeding, history, alerts, config, status, error } = state;
  const gate = environment?.gate_state || 'Unsafe';

  return (
    <section className="min-w-[980px] flex-1 rounded-[2rem] border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-sky-950/40 backdrop-blur">
      <header className="flex items-center justify-between">
        <AquaLogo />
        <div className="flex items-center gap-3">
          <div className={`rounded-full border px-4 py-2 text-sm font-semibold ${
            gate === 'Safe'
              ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
              : 'border-red-400/30 bg-red-500/10 text-red-200'
          }`}>
            <span className={`mr-2 inline-block size-2 rounded-full ${gate === 'Safe' ? 'bg-emerald-400 shadow-[0_0_14px_#22c55e]' : 'bg-red-400 shadow-[0_0_14px_#ef4444]'}`} />
            Gate {gate === 'Safe' ? 'Safe - feeding permitted' : 'Unsafe - feeding withheld'}
          </div>
          <button
            type="button"
            onClick={() => setAdmin((value) => !value)}
            className={`rounded-full border px-4 py-2 text-sm font-bold transition ${
              admin
                ? 'border-violet-300/40 bg-violet-400/20 text-violet-100'
                : 'border-white/15 bg-white/[0.05] text-slate-200 hover:bg-white/10'
            }`}
          >
            {admin ? 'Admin view' : 'Caretaker view'}
          </button>
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

      {error && (
        <div className="mt-4 rounded-2xl border border-red-300/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
          Backend unreachable: {error}
        </div>
      )}
      {state.loading && !error && (
        <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-400">
          Loading telemetry from 127.0.0.1:8000…
        </div>
      )}

      <EnvironmentGatePanel environment={environment} schedule={feeding?.schedule} />
      <FeedingSessionPanel
        feeding={feeding}
        now={now}
        admin={admin}
        onTestSession={onTestSession}
        testing={testing}
        notice={notice}
      />
      <DetectionEvidencePanel status={status} />

      <div className="mt-6 grid grid-cols-[1fr_340px] gap-5">
        <main className="space-y-5">
          <div className="grid grid-cols-2 gap-5">
            <HistoryPanel history={history} />
            <div className="rounded-3xl border border-white/10 bg-slate-950/45 p-4">
              <h3 className="text-lg font-semibold text-white">Detection checks</h3>
              <div className="mt-3 space-y-2 text-xs text-slate-400">
                <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                  <span>Environmental gate</span>
                  <span className={gate === 'Safe' ? 'text-emerald-200' : 'text-red-200'}>{gate}</span>
                </div>
                <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                  <span>Feeding-zone ROI</span>
                  <span className="text-emerald-200">Clear</span>
                </div>
                <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                  <span>Observation window</span>
                  <span className="text-white">{OBSERVATION_WINDOW}</span>
                </div>
                <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                  <span>Low-confidence reads</span>
                  <span className="text-amber-200">Held (fail-safe)</span>
                </div>
              </div>
            </div>
          </div>
        </main>
        <aside className="space-y-5">
          <AlertsPanel alerts={alerts} />
          <SetupCard config={config} />
        </aside>
      </div>

      <NotImplementedNote />
      {admin && <AdminPanel config={config} onToggleSimulated={onToggleSimulated} saving={savingConfig} />}
    </section>
  );
}

function App() {
  const [state, reload] = useTelemetry(2000);
  const now = useNow(1000);
  const [admin, setAdmin] = React.useState(false);
  const [testing, setTesting] = React.useState(false);
  const [savingConfig, setSavingConfig] = React.useState(false);
  const [notice, setNotice] = React.useState(null);

  const onTestSession = async () => {
    setTesting(true);
    setNotice(null);
    try {
      const result = await api.testSession();
      setNotice(`TEST TRIGGER started session #${result.session_id} at a strict ${result.observation_window_s} s window.`);
      await reload();
    } catch (error) {
      setNotice(`Could not start test session: ${error.message}`);
    } finally {
      setTesting(false);
    }
  };

  const onToggleSimulated = async () => {
    setSavingConfig(true);
    setNotice(null);
    try {
      const next = await api.saveConfig({ simulate_pellets: !state.config?.simulate_pellets });
      setNotice(`Feeding zone simulation ${next.simulate_pellets ? 'on' : 'off'}.`);
      await reload();
    } catch (error) {
      setNotice(`Could not change simulation: ${error.message}`);
    } finally {
      setSavingConfig(false);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,.28),transparent_34%),linear-gradient(135deg,#020617,#0f172a_48%,#062134)] px-6 py-8 text-slate-100">
      <div className="mx-auto max-w-[1800px]">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-100">
              <Fish className="size-4 text-cyan-300" /> YOLOv8 feed-pellet detection · ESP32 sensing · GSM/SMS alerts
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-white md:text-5xl">
              Tilapiers: A YOLOv8-Based Intelligent Behavior Analysis and Automated Feeding System for Tilapia
            </h1>
            <p className="mt-3 max-w-3xl text-slate-300">
              Feeding happens only when temperature and dissolved oxygen are classified Safe. A reference starter
              dose is dispensed in fixed increments of 25%, and visible pellet depletion over each five-minute
              observation window decides whether to continue, reduce or stop.
            </p>
          </div>
        </div>

        <Dashboard
          state={state}
          now={now}
          admin={admin}
          setAdmin={setAdmin}
          onTestSession={onTestSession}
          testing={testing}
          notice={notice}
          onToggleSimulated={onToggleSimulated}
          savingConfig={savingConfig}
        />
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
