// Renders an agent answer: paragraphs, "* " / "- " / "1. " lists, **bold**, and bare URLs
// as links that open in a new tab. Built from React elements (never innerHTML), so
// nothing in an answer can inject markup.

const URL_RE = /https?:\/\/[^\s<>()"']+[^\s<>()"'.,;:!?]/g;
const BOLD_RE = /\*\*(.+?)\*\*/g;

function withLinks(text, keyPrefix) {
  const parts = [];
  let last = 0;
  for (const match of text.matchAll(URL_RE)) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push(
      <a key={`${keyPrefix}-u${match.index}`} href={match[0]} target="_blank" rel="noopener noreferrer">
        {match[0]}
      </a>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function inline(text, keyPrefix) {
  const parts = [];
  let last = 0;
  for (const match of text.matchAll(BOLD_RE)) {
    if (match.index > last) parts.push(...withLinks(text.slice(last, match.index), `${keyPrefix}-${last}`));
    parts.push(<strong key={`${keyPrefix}-b${match.index}`}>{withLinks(match[1], `${keyPrefix}-b${match.index}`)}</strong>);
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(...withLinks(text.slice(last), `${keyPrefix}-${last}`));
  return parts;
}

const BULLET = /^\s*[*-]\s+/;
const NUMBERED = /^\s*\d+[.)]\s+/;

/** Group lines into paragraphs and lists. */
function blocks(text) {
  const out = [];
  for (const line of text.replace(/\r\n/g, "\n").split("\n")) {
    const kind = BULLET.test(line) ? "ul" : NUMBERED.test(line) ? "ol" : line.trim() ? "p" : "gap";
    const prev = out[out.length - 1];
    if (kind === "gap") {
      if (prev) prev.closed = true;
    } else if (kind === "p") {
      if (prev && prev.kind === "p" && !prev.closed) prev.lines.push(line.trim());
      else out.push({ kind, lines: [line.trim()] });
    } else {
      const item = line.replace(kind === "ul" ? BULLET : NUMBERED, "");
      if (prev && prev.kind === kind) prev.lines.push(item);
      else out.push({ kind, lines: [item] });
    }
  }
  return out;
}

export default function AnswerText({ text }) {
  return (
    <div className="answer-text">
      {blocks(text).map((block, i) => {
        if (block.kind === "p") {
          return (
            <p key={i}>
              {block.lines.flatMap((line, j) => [j > 0 && <br key={`br${j}`} />, ...inline(line, `${i}-${j}`)])}
            </p>
          );
        }
        const List = block.kind;
        return (
          <List key={i}>
            {block.lines.map((line, j) => (
              <li key={j}>{inline(line, `${i}-${j}`)}</li>
            ))}
          </List>
        );
      })}
    </div>
  );
}
