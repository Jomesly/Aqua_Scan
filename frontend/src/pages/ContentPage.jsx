import { Card, LoadError, Loading } from '../components/ui';
import Markdown from '../components/Markdown';
import { useResource } from '../lib/api';
import { fmtDateTime } from '../lib/format';

export default function ContentPage({ contentKey }) {
  const { data, error, loading, reload } = useResource(`/api/content/${contentKey}`, { deps: [contentKey] });
  if (loading && !data) return <Loading />;
  if (error) return <LoadError error={error} onRetry={reload} />;
  return (
    <div className="stack narrow">
      <div className="page-head">
        <span className="eyebrow">{contentKey === 'faqs' ? 'Help' : 'About Us'}</span>
        <h1>{data.title}</h1>
      </div>
      <Card><Markdown text={data.body_md} /></Card>
      <p className="subtle">Last updated {fmtDateTime(data.updated_at)}. Administrators can edit this page in Maintenance.</p>
    </div>
  );
}
