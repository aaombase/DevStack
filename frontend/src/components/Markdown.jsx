// Renders the tiny markdown subset the backend emits (#/## headings, "- " bullets,
// **bold**) as React elements. No HTML injection: everything is plain text nodes.

function inline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  );
}

export default function Markdown({ source }) {
  const nodes = [];
  let list = null;
  const flush = () => {
    if (list) nodes.push(<ul key={`ul${nodes.length}`}>{list}</ul>);
    list = null;
  };

  source.split("\n").forEach((raw, i) => {
    const bullet = raw.match(/^(\s*)- (.*)$/);
    if (bullet) {
      list ??= [];
      list.push(
        <li key={i} className={bullet[1].length ? "nested" : undefined}>{inline(bullet[2])}</li>,
      );
      return;
    }
    flush();
    if (raw.startsWith("## ")) nodes.push(<h4 key={i}>{inline(raw.slice(3))}</h4>);
    else if (raw.startsWith("# ")) nodes.push(<h3 key={i}>{inline(raw.slice(2))}</h3>);
    else if (raw.trim()) nodes.push(<p key={i}>{inline(raw)}</p>);
  });
  flush();
  return <div className="markdown">{nodes}</div>;
}
