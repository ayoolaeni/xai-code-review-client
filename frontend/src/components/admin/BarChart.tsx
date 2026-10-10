/** Simple accessible horizontal bar chart drawn with divs (no chart library). */
export function BarChart({
  title,
  data,
  format = (v: number) => String(v),
}: {
  title: string;
  data: { label: string; value: number }[];
  format?: (v: number) => string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <figure className="card">
      <figcaption className="font-semibold">{title}</figcaption>
      {data.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No data yet.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {data.map((d) => (
            <li key={d.label} className="grid grid-cols-[110px_1fr_auto] items-center gap-2 text-sm">
              <span className="truncate" title={d.label}>
                {d.label}
              </span>
              <span className="h-3 rounded bg-canvas" aria-hidden="true">
                <span className="block h-3 rounded bg-brand" style={{ width: `${(d.value / max) * 100}%` }} />
              </span>
              <span className="tabular-nums">{format(d.value)}</span>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}

/** Vertical bars per day. */
export function DailyChart({ title, data }: { title: string; data: { date: string; value: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <figure className="card">
      <figcaption className="font-semibold">{title}</figcaption>
      {data.length === 0 ? (
        <p className="mt-2 text-sm text-muted">No data yet.</p>
      ) : (
        <>
          <div className="mt-3 flex h-32 items-end gap-1" aria-hidden="true">
            {data.map((d) => (
              <div key={d.date} className="flex flex-1 flex-col justify-end" title={`${d.date}: ${d.value}`}>
                <div
                  className="rounded-t bg-brand"
                  style={{ height: `${(d.value / max) * 100}%`, minHeight: d.value ? 2 : 0 }}
                />
              </div>
            ))}
          </div>
          <p className="mt-1 flex justify-between text-xs text-muted">
            <span>{data[0]?.date}</span>
            <span>{data[data.length - 1]?.date}</span>
          </p>
          <table className="sr-only">
            <caption>{title}</caption>
            <tbody>
              {data.map((d) => (
                <tr key={d.date}>
                  <th scope="row">{d.date}</th>
                  <td>{d.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </figure>
  );
}
