import { Link } from 'react-router-dom';
import { Camera, ChevronRight, Fish, PencilLine, Stethoscope } from 'lucide-react';
import { Empty, LoadError, Loading, Notice, Stat } from '../components/ui';
import { DemoTag, HealthBadge, ReadinessBadge } from '../components/Status';
import { useResource } from '../lib/api';
import { can, useAuth } from '../lib/auth';
import { fmtDate, fmtNum } from '../lib/format';

function PondCard({ item }) {
  const { pond, latest, drafts } = item;
  const tone = latest?.health === 'Refer to technician' ? 'crit' : latest?.health === 'Watch' ? 'attn' : '';
  return (
    <article className={`card pond-card ${tone}`}>
      <div className="pond-card-head">
        <div>
          <h2><Link to={`/ponds/${pond.id}`} className="stretched">{pond.name}</Link></h2>
          <p className="subtle">{pond.setup || 'Pond'}{pond.stocked_count ? ` · ${pond.stocked_count.toLocaleString()} fish stocked` : ''}</p>
        </div>
        {pond.source === 'demo' && <DemoTag />}
      </div>
      {latest ? (
        <>
          <div className="status-pair">
            <div><span className="k">Health</span><HealthBadge value={latest.health} /></div>
            <div><span className="k">Harvest readiness</span><ReadinessBadge value={latest.readiness} /></div>
          </div>
          <div className="stats three">
            <Stat label="Avg weight" value={fmtNum(latest.avg_weight_g, 0)} unit="g" />
            <Stat label="Biomass" value={fmtNum(latest.biomass_kg, 0)} unit="kg" />
            <Stat label="Days of culture" value={fmtNum(latest.days_of_culture, 0)} />
          </div>
          <p className="subtle">Last round {fmtDate(latest.sampled_at)}{latest.refer ? ` · ${latest.refer} fish referred` : ''}</p>
        </>
      ) : (
        <p className="muted small">No completed sampling round yet.</p>
      )}
      {drafts.length > 0 && (
        <Link className="btn sm draft-link" to={`/rounds/${drafts[0]}`}>
          <PencilLine size={16} aria-hidden="true" /> Continue draft round
        </Link>
      )}
      <ChevronRight className="pond-card-chev" size={20} aria-hidden="true" />
    </article>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useResource('/api/dashboard', { interval: 30000 });
  if (loading && !data) return <Loading />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;
  const hour = new Date().getHours();
  const greet = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  return (
    <div className="stack">
      <div className="page-head row-between wrap">
        <div>
          <span className="eyebrow">Dashboard</span>
          <h1>{greet}</h1>
          <p>Latest Health and Harvest readiness status of each pond, from its most recent completed sampling round.</p>
        </div>
        <div className="page-actions">
          {can.review(user) && data.review_count > 0 && (
            <Link className="btn" to="/review"><Stethoscope size={18} aria-hidden="true" />{data.review_count} fish to review</Link>
          )}
          {can.sample(user) && (
            <Link className="btn primary" to="/sample"><Camera size={18} aria-hidden="true" />Start sampling round</Link>
          )}
        </div>
      </div>

      {!data.screener?.available && (
        <Notice kind="error"><strong>Screening model unavailable.</strong> {data.screener?.error} Fish will be marked “Not screened”.</Notice>
      )}
      {(!data.thresholds_confirmed || data.weight_model?.provisional) && (
        <Notice kind="warn">
          {!data.thresholds_confirmed && <>Status cutoffs are <strong>provisional</strong> until confirmed with the BFAR technician. </>}
          {data.weight_model?.provisional && <>Weights use the <strong>provisional length–weight curve</strong> until the regression is fitted. </>}
          {can.admin(user) && <Link to="/maintenance">Open Maintenance</Link>}
        </Notice>
      )}

      {data.ponds.length === 0 ? (
        <Empty icon={Fish} title="No ponds yet">
          {can.admin(user) ? 'Add the first pond in Maintenance.' : 'Ask the administrator to add your ponds.'}
        </Empty>
      ) : (
        <div className="pond-grid">
          {data.ponds.map((p) => <PondCard key={p.pond.id} item={p} />)}
        </div>
      )}
    </div>
  );
}
