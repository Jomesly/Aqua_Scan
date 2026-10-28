import { Link } from 'react-router-dom';
import { Bell, Camera, CloudSun, Droplets, Fish, Plus, Waves } from 'lucide-react';
import { useResource } from '../lib/api';
import { fmtAgo, fmtDay, fmtNum, isSynthetic, SOURCE_LABEL } from '../lib/format';
import { Card, Empty, LoadError, Loading } from '../components/ui';
import { EnvBadge, HealthBadge, ReadinessBadge } from '../components/Status';
import { AlertRow } from './Alerts';

function attention(p) {
  const env = p.environment.state;
  const health = p.latest_round?.health?.status;
  if (env === 'Critical' || health === 'Refer to technician') return 'crit';
  if (env !== 'Good' || health === 'Watch') return 'attn';
  return '';
}

function PondCard({ pond }) {
  const env = pond.environment;
  const lr = pond.latest_round;
  const cls = attention(pond);
  return (
    <Link to={`/ponds/${pond.id}`} className={`card pond-card ${cls}`} aria-label={`${pond.name}: open pond details`}>
      <div className="pond-card-head">
        <div>
          <h2>{pond.name}</h2>
          <p className="subtle">Day {fmtNum(pond.days_of_culture, 0)} of culture{pond.location ? ` · ${pond.location}` : ''}</p>
        </div>
        <EnvBadge value={env.state} />
      </div>

      <div className="row-between">
        <div className="temp-hero">
          <span className="value">{env.stale ? '—' : fmtNum(env.temperature_c)}</span>
          <span className="unit">°C</span>
        </div>
        <div className="stack" style={{ gap: 4, justifyItems: 'end' }}>
          <span className="subtle">{env.stale ? `Last reading ${fmtAgo(env.reading_ts)}` : `Updated ${fmtAgo(env.reading_ts)}`}</span>
          {env.source && isSynthetic(env.source) && <span className="tag warn">{SOURCE_LABEL[env.source]}</span>}
        </div>
      </div>

      <div className="status-rows">
        <div className="status-row">
          <span className="k"><Fish size={16} aria-hidden="true" />Fish health</span>
          {lr ? <HealthBadge value={lr.health.status} /> : <span className="subtle">No sampling yet</span>}
        </div>
        <div className="status-row">
          <span className="k"><Waves size={16} aria-hidden="true" />Harvest readiness</span>
          {lr ? <ReadinessBadge value={lr.readiness} /> : <span className="subtle">—</span>}
        </div>
        <div className="status-row">
          <span className="k"><Droplets size={16} aria-hidden="true" />Algae reported</span>
          <span className="small" style={{ fontWeight: 600 }}>{env.algae_active ? 'Yes, recently' : 'No'}</span>
        </div>
      </div>

      <p className="subtle" style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        {lr ? `Last sampled ${fmtDay(lr.sampled_at)} (day ${fmtNum(lr.days_of_culture, 0)})` : 'Start a sampling round to assess health and readiness.'}
      </p>
    </Link>
  );
}

export default function Overview() {
  const { data, error, loading, reload } = useResource('/api/overview', { interval: 5000 });
  if (loading && !data) return <Loading label="Loading ponds" />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;

  const ponds = data.ponds;
  const season = ponds[0]?.environment?.season;
  const needs = ponds.filter((p) => attention(p)).length;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow"><CloudSun size={15} aria-hidden="true" />{season ? `${season} season` : 'Season'}</div>
          <h1>Ponds</h1>
          <p>
            {ponds.length === 0
              ? 'Add your first pond in Settings to start monitoring.'
              : needs
                ? `${needs} of ${ponds.length} ponds need attention.`
                : `All ${ponds.length} ponds are within limits.`}
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn primary" to="/sample"><Camera size={18} aria-hidden="true" />New sampling round</Link>
        </div>
      </div>

      {ponds.length === 0 ? (
        <Card>
          <Empty icon={Fish} title="No ponds yet" action={<Link className="btn primary" to="/settings#ponds"><Plus size={18} aria-hidden="true" />Add a pond</Link>}>
            Each pond gets its own temperature log, sampling rounds and harvest record.
          </Empty>
        </Card>
      ) : (
        <div className="grid-main">
          <div className="pond-grid" style={{ alignContent: 'start' }}>
            {ponds.map((p) => <PondCard key={p.id} pond={p} />)}
          </div>
          <Card title="Recent alerts" icon={Bell} flush actions={<Link to="/alerts" className="btn sm ghost">View all</Link>}>
            {data.notifications.length === 0 ? (
              <Empty title="No alerts yet">Alerts appear when the environment changes state or a round needs review.</Empty>
            ) : (
              <ul className="alert-list">
                {data.notifications.map((n) => <AlertRow key={n.id} note={n} compact ponds={ponds} />)}
              </ul>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
