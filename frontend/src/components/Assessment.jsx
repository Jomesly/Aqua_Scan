import { CheckCircle2, Circle, XCircle } from 'lucide-react';
import { HealthBadge, ProvisionalTag, ReadinessBadge } from './Status';
import { Card, Notice, Stat } from './ui';
import { fmtNum, fmtPct } from '../lib/format';

export function CriteriaList({ criteria }) {
  if (!criteria?.length) return null;
  return (
    <ul className="checklist">
      {criteria.map((c) => {
        const Icon = c.passed === true ? CheckCircle2 : c.passed === false ? XCircle : Circle;
        const cls = c.passed === true ? 'ok' : c.passed === false ? 'no' : 'na';
        return (
          <li key={c.key}>
            <Icon size={18} className={cls} aria-hidden="true" />
            <span>
              {c.label}
              <span className="sr-only">{c.passed ? ' met' : ' not met'}</span>
            </span>
            <span className="val">{c.value}<small>{c.target}</small></span>
          </li>
        );
      })}
    </ul>
  );
}

/** The round-level summary: average weight, biomass, Health and Harvest readiness. */
export function RoundAssessment({ a, live }) {
  const s = a.summary;
  return (
    <div className="stack">
      {live && (
        <Notice kind="info">Live preview: statuses update as photos are processed. They are saved when the round is completed.</Notice>
      )}
      <div className="row wrap gap-s">
        {!a.thresholds_confirmed && <ProvisionalTag>Provisional cutoffs</ProvisionalTag>}
        {a.weight_model?.provisional
          ? <ProvisionalTag>Provisional weight model (not fitted)</ProvisionalTag>
          : <span className="tag">Weight model: {a.weight_model?.label}</span>}
        <span className="tag">Screening: {a.screener}</span>
      </div>
      <div className="stats four card">
        <Stat label="Fish" value={s.n_fish} title={`${s.n_screened} screened, ${s.n_measured} measured`} />
        <Stat label="Average weight" value={fmtNum(s.avg_weight_g, 0)} unit="g" />
        <Stat label="Biomass estimate" value={fmtNum(s.biomass_kg, 0)} unit="kg"
          title={s.count_used ? `Average weight × ${s.count_used} fish` : 'Needs the stocked or counted number of fish'} />
        <Stat label="Mean K" value={fmtNum(s.mean_k, 2)} />
      </div>
      <div className="grid-2">
        <Card title="Health status" hint={`${s.n_screened} of ${s.n_fish} fish screened`}>
          <HealthBadge value={a.health.status} size="lg" />
          <div className="bar-list" style={{ marginTop: 12 }}>
            {Object.entries(s.status_counts).map(([k, v]) => (
              <div key={k} className="bar-row">
                <HealthBadge value={k} />
                <span className="bar-track"><span className="bar-fill" style={{ width: `${s.n_fish ? (v / s.n_fish) * 100 : 0}%` }} /></span>
                <span className="num">{v}</span>
              </div>
            ))}
          </div>
          <p className="subtle" style={{ marginTop: 8 }}>
            Pond is Watch at {fmtPct(a.thresholds.pond_watch_share)} of fish Watch or Refer, and Refer at
            {' '}{fmtPct(a.thresholds.pond_refer_share)} or any referred fish. At least
            {' '}{fmtPct(a.thresholds.min_screened_share)} of sampled fish must be screened; otherwise “No data”.
          </p>
        </Card>
        <Card title="Harvest readiness" hint={`${a.readiness.met ?? 0} of 5 indicators met`}>
          <ReadinessBadge value={a.readiness.status} size="lg" />
          <CriteriaList criteria={a.readiness.criteria} />
          <ul className="reasons">{a.readiness.notes?.map((n) => <li key={n}>{n}</li>)}</ul>
        </Card>
      </div>
    </div>
  );
}
