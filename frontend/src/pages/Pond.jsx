import { Link, useParams } from 'react-router-dom';
import { Camera, ChevronLeft, LineChart as LineIcon, ListChecks } from 'lucide-react';
import { Card, Empty, LoadError, Loading, Stat } from '../components/ui';
import { DemoTag, HealthBadge, ReadinessBadge } from '../components/Status';
import { GrowthChart } from '../components/charts';
import { CriteriaList } from '../components/Assessment';
import { useResource } from '../lib/api';
import { can, useAuth } from '../lib/auth';
import { fmtDate, fmtNum, fmtPct } from '../lib/format';

export default function Pond() {
  const { pondId } = useParams();
  const { user } = useAuth();
  const { data, error, loading, reload } = useResource(`/api/ponds/${pondId}`, { deps: [pondId] });
  if (loading && !data) return <Loading />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;
  const { pond, latest, rounds, growth, points } = data;
  const a = latest?.assessment;
  const t = a?.thresholds;

  return (
    <div className="stack">
      <Link to="/" className="back-link"><ChevronLeft size={18} aria-hidden="true" />Dashboard</Link>
      <div className="page-head row-between wrap">
        <div>
          <span className="eyebrow">Pond {pond.source === 'demo' && <DemoTag />}</span>
          <h1>{pond.name}</h1>
          <p>{[pond.setup, pond.location, pond.stocked_at && `stocked ${fmtDate(pond.stocked_at)}`,
            pond.stocked_count && `${pond.stocked_count.toLocaleString()} fish`].filter(Boolean).join(' · ')}</p>
        </div>
        {can.sample(user) && (
          <Link className="btn primary" to={`/sample?pond=${pond.id}`}><Camera size={18} aria-hidden="true" />New sampling round</Link>
        )}
      </div>

      {a ? (
        <div className="grid-2">
          <Card title="Health status" hint={`Round of ${fmtDate(latest.sampled_at)}`}>
            <HealthBadge value={a.health.status} size="lg" />
            <div className="stats three" style={{ marginTop: 12 }}>
              <Stat label="Fish screened" value={a.health.n} />
              <Stat label="Watch or Refer" value={fmtPct(a.health.watch_share)} />
              <Stat label="Referred" value={a.health.refer_count} />
            </div>
          </Card>
          <Card title="Harvest readiness" hint={`${a.readiness.met ?? 0} of 5 indicators met`}>
            <ReadinessBadge value={a.readiness.status} size="lg" />
            <CriteriaList criteria={a.readiness.criteria} />
          </Card>
        </div>
      ) : (
        <Empty icon={ListChecks} title="No completed round yet">Statuses appear after the first sampling round is completed.</Empty>
      )}

      {a && (
        <div className="stats four card">
          <Stat label="Average weight" value={fmtNum(a.summary.avg_weight_g, 0)} unit="g" />
          <Stat label="Biomass estimate" value={fmtNum(a.summary.biomass_kg, 0)} unit="kg" title="Average estimated weight × stocked or counted fish" />
          <Stat label="Weight CV" value={fmtPct(a.summary.cv)} />
          <Stat label="Mean K" value={fmtNum(a.summary.mean_k, 2)} />
        </div>
      )}

      <Card title="Growth" icon={LineIcon}
        hint={growth.method === 'polynomial'
          ? `Degree-2 curve over ${growth.n_rounds} rounds (R² ${fmtNum(growth.poly.r2, 3)}). Shown over the observed days only; not a forecast.`
          : `Specific growth rate ${growth.latest_sgr != null ? `${fmtNum(growth.latest_sgr, 2)} %/day` : 'needs 2 rounds'}. The curve appears from ${t?.growth_poly_min_rounds ?? 5} rounds.`}>
        <GrowthChart points={points} poly={growth.poly} target={t?.target_weight_g} />
      </Card>

      <Card title="Sampling-round history" flush>
        {rounds.length === 0 ? <p className="card-pad muted">No rounds yet.</p> : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr><th>Date</th><th className="num">Day</th><th className="num">Fish</th><th className="num">Avg g</th>
                  <th>Health</th><th>Readiness</th><th>Technician</th></tr>
              </thead>
              <tbody>
                {rounds.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/rounds/${r.id}`}>{fmtDate(r.sampled_at)}</Link>
                      {r.status === 'draft' && <span className="tag">Draft</span>}
                      {!r.board_mode && <span className="tag">No board</span>}</td>
                    <td className="num">{fmtNum(r.days_of_culture, 0)}</td>
                    <td className="num">{r.n_fish}</td>
                    <td className="num">{fmtNum(r.avg_weight_g, 0)}</td>
                    <td><HealthBadge value={r.health} /></td>
                    <td><ReadinessBadge value={r.readiness} /></td>
                    <td className="small">{r.tech_health || r.tech_readiness
                      ? `${r.tech_health || '—'} / ${r.tech_readiness || '—'}` : <span className="subtle">not yet</span>}</td>
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
