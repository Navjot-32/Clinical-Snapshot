import type { ReactNode } from "react";
import type { SectionState } from "@/lib/types";

/** Empty is not one state but two, and they mean opposite things.
 *
 * "No allergy records in the source" is a statement about the data.
 * "Records exist but none can be shown" is a warning that something is missing.
 * Rendering the same blank box for both would let a reader infer the first when
 * the second is true, which is the more dangerous mistake. */
function EmptyState({ state, noun, withheldCount }: { state: SectionState; noun: string; withheldCount: number }) {
  if (state === "all-withheld") {
    return (
      <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
        {withheldCount} {noun} {withheldCount === 1 ? "record exists" : "records exist"} in the source data, but
        none could be shown as current. See data quality below.
      </p>
    );
  }
  return <p className="px-1 py-2 text-sm text-slate-500">No {noun} records in the source data.</p>;
}

export function Section({
  title,
  state,
  noun,
  withheldCount,
  count,
  children,
}: {
  title: string;
  state: SectionState;
  noun: string;
  withheldCount: number;
  count: number;
  children: ReactNode;
}) {
  const isEmpty = count === 0;

  const headingId = `section-${title.toLowerCase().replace(/\s+/g, "-")}`;

  return (
    <section aria-labelledby={headingId} className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex items-baseline justify-between border-b border-slate-200 px-4 py-2.5">
        <h2 id={headingId} className="text-sm font-semibold uppercase tracking-wide text-slate-700">
          {title}
        </h2>
        {withheldCount > 0 && (
          <span
            aria-label={`${withheldCount} ${noun} record(s) withheld from this section`}
            className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-900 ring-1 ring-inset ring-amber-300"
          >
            {withheldCount} withheld
          </span>
        )}
      </header>
      <div className="px-4 py-3">
        {isEmpty ? <EmptyState state={state} noun={noun} withheldCount={withheldCount} /> : children}
      </div>
    </section>
  );
}

export function Row({ children }: { children: ReactNode }) {
  return <div className="border-b border-slate-100 py-2.5 last:border-0 last:pb-0 first:pt-0">{children}</div>;
}
