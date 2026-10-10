/** A small excerpt (±3 lines) of the code with the finding's lines highlighted. Plain text only. */
export function CodeExcerpt({
  code,
  start,
  end,
  context = 3,
}: {
  code: string;
  start: number;
  end: number;
  context?: number;
}) {
  const lines = code.split("\n");
  const from = Math.max(1, start - context);
  const to = Math.min(lines.length, end + context);
  const width = String(to).length;
  return (
    <pre className="code-block" aria-label={`Code excerpt, lines ${from} to ${to}`}>
      {lines.slice(from - 1, to).map((text, i) => {
        const n = from + i;
        const hit = n >= start && n <= end;
        return (
          <div key={n} className={hit ? "-mx-3 bg-amber-400/25 px-3" : undefined}>
            <span className="select-none text-slate-400">{String(n).padStart(width, " ")} │ </span>
            {text || " "}
            {hit && <span className="sr-only"> (highlighted)</span>}
          </div>
        );
      })}
    </pre>
  );
}
