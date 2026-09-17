import type { DataQuality } from "@/lib/types";

/** Notes name the record and the reason, never the withheld value. A retracted
 * result printed here would be back in front of a clinician, which is exactly what
 * withholding it was meant to prevent. */
export function DataQualityPanel({ data }: { data: DataQuality }) {
  const total = data.notes.length;

  if (total === 0) {
    return (
      <section className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
        No data quality problems were found in this bundle.
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <details open>
        <summary className="cursor-pointer border-b border-slate-200 px-4 py-2.5 text-sm font-semibold uppercase tracking-wide text-slate-700">
          Data quality · {total} {total === 1 ? "record" : "records"} not shown
        </summary>
        <ul className="divide-y divide-slate-100">
          {data.notes.map((note) => (
            <li key={`${note.resourceType}-${note.resourceId}`} className="px-4 py-2 text-sm">
              <span className="font-mono text-[12px] text-slate-500">
                {note.resourceType}/{note.resourceId}
              </span>
              {note.section && <span className="ml-2 text-[11px] uppercase tracking-wide text-slate-400">{note.section}</span>}
              <p className="text-slate-700">{note.reason}</p>
            </li>
          ))}
        </ul>
        {data.unparsedTotal > 0 && (
          <p className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
            {data.unparsedTotal} resource(s) could not be parsed at all and were excluded from every section.
          </p>
        )}
      </details>
    </section>
  );
}
