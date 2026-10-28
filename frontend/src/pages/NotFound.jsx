import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { Card, Empty } from '../components/ui';

export default function NotFound() {
  return (
    <Card>
      <Empty icon={Compass} title="Page not found" action={<Link className="btn primary" to="/">Back to ponds</Link>}>
        The page you were looking for doesn't exist.
      </Empty>
    </Card>
  );
}
