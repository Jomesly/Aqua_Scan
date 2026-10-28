import { Link } from 'react-router-dom';
import { AlertTriangle, Bell, CheckCheck, Info, OctagonAlert } from 'lucide-react';
import { api, useResource } from '../lib/api';
import { fmtDateTime } from '../lib/format';
import { Button, Card, Empty, LoadError, Loading, Notice } from '../components/ui';
import { useSystem } from '../components/Shell';

const SEVERITY = {
  critical: { tone: 'critical', Icon: OctagonAlert, label: 'Critical' },
  warning: { tone: 'moderate', Icon: AlertTriangle, label: 'Warning' },
  info: { tone: 'info', Icon: Info, label: 'Info' },
};

const DELIVERY = {
  delivered: { tone: 'good', text: 'delivered' },
  sent: { tone: 'good', text: 'sent' },
  failed: { tone: 'critical', text: 'failed' },
  not_sent: { tone: 'unknown', text: 'not sent' },
};

export function AlertRow({ note, compact, ponds, onAck }) {
  const sev = SEVERITY[note.severity] || SEVERITY.info;
  const pond = ponds?.find((p) => p.id === note.pond_id);
  return (
    <li className={`alert-item ${compact ? 'compact' : ''} ${note.acknowledged ? '' : 'unread'}`}>
      <span className={`alert-icon tone-${sev.tone}`}>
        <sev.Icon size={18} aria-hidden="true" />
      </span>
      <div style={{ minWidth: 0 }}>
        <div className="row-between" style={{ alignItems: 'flex-start' }}>
          <div className="alert-title">
            <span className="sr-only">{sev.label}: </span>{note.title}
          </div>
          {onAck && !note.acknowledged && (
            <button type="button" className="btn sm ghost" onClick={() => onAck(note.id)}>Mark read</button>
          )}
        </div>
        {!compact && <p className="small muted" style={{ marginTop: 4 }}>{note.message}</p>}
        <div className="alert-meta">
          <span>{fmtDateTime(note.ts)}</span>
          {pond && <Link to={`/ponds/${pond.id}`}>{pond.name}</Link>}
          {!compact && note.deliveries.map((d) => {
            const spec = DELIVERY[d.status] || DELIVERY.not_sent;
            return (
              <span key={d.channel} className={`tag tone-${spec.tone}`} title={d.detail || ''}>
                {d.channel}: {spec.text}{d.detail ? ` (${d.detail})` : ''}
              </span>
            );
          })}
        </div>
      </div>
    </li>
  );
}

export default function Alerts() {
  const { data, error, loading, reload } = useResource('/api/notifications?limit=200', { interval: 8000 });
  const { data: ponds } = useResource('/api/ponds');
  const { reloadUnread } = useSystem();

  const ack = async (id) => {
    await api.post(`/api/notifications/${id}/ack`);
    reload();
    reloadUnread?.();
  };
  const ackAll = async () => {
    await api.post('/api/notifications/ack-all');
    reload();
    reloadUnread?.();
  };

  if (loading && !data) return <Loading label="Loading alerts" />;
  if (error && !data) return <LoadError error={error} onRetry={reload} />;
  const unread = data.notifications.filter((n) => !n.acknowledged).length;
  const ch = data.channel;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p>Environment state changes, probe outages, and sampling rounds that need a technician's review.</p>
        </div>
        <div className="page-actions">
          <Button icon={CheckCheck} onClick={ackAll} disabled={!unread}>Mark all read</Button>
        </div>
      </div>

      <Notice kind={ch.ready ? 'success' : 'info'}>
        <strong>Delivery channel: {ch.channel === 'none' ? 'dashboard only' : ch.channel}.</strong> {ch.detail}{' '}
        <Link to="/settings#notifications">Notification settings</Link>
      </Notice>

      <Card flush>
        {data.notifications.length === 0 ? (
          <Empty icon={Bell} title="No alerts yet">You'll see alerts here when a pond's state changes.</Empty>
        ) : (
          <ul className="alert-list">
            {data.notifications.map((n) => <AlertRow key={n.id} note={n} ponds={ponds} onAck={ack} />)}
          </ul>
        )}
      </Card>
    </>
  );
}
