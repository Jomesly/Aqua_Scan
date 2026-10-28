/** Minimal, safe markdown for the FAQs and About pages: headings, lists, bold, italics,
 *  paragraphs. Renders React elements only, so no HTML is injected. */

function inline(text, keyBase) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0;
  let m;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    out.push(tok.startsWith('**')
      ? <strong key={`${keyBase}-${i++}`}>{tok.slice(2, -2)}</strong>
      : <em key={`${keyBase}-${i++}`}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({ text }) {
  const blocks = [];
  let list = null;
  const flush = () => {
    if (list) blocks.push(list);
    list = null;
  };
  (text || '').split('\n').forEach((raw, n) => {
    const line = raw.trimEnd();
    const ul = line.match(/^\s*-\s+(.*)/);
    const ol = line.match(/^\s*\d+\.\s+(.*)/);
    if (ul || ol) {
      const type = ul ? 'ul' : 'ol';
      if (!list || list.type !== type) { flush(); list = { type, items: [] }; }
      list.items.push((ul || ol)[1]);
      return;
    }
    flush();
    if (!line.trim()) return;
    const h = line.match(/^(#{1,3})\s+(.*)/);
    if (h) blocks.push({ type: `h${h[1].length + 1}`, text: h[2], n });
    else blocks.push({ type: 'p', text: line, n });
  });
  flush();
  return (
    <div className="prose">
      {blocks.map((b, i) => {
        if (b.type === 'ul' || b.type === 'ol') {
          const L = b.type;
          return <L key={i}>{b.items.map((it, j) => <li key={j}>{inline(it, `${i}-${j}`)}</li>)}</L>;
        }
        const T = b.type;
        return <T key={i}>{inline(b.text, i)}</T>;
      })}
    </div>
  );
}
