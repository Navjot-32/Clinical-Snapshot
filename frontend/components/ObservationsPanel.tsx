import type { ObservationSummary, Section as SectionData } from "@/lib/types";
import { ConceptLabel } from "./ui/ConceptLabel";
import { FlagList } from "./ui/Badge";
import { Row, Section } from "./ui/Section";

/** One list, ordered by recency. The bundle only categorises one of these as a
 * vital sign, so splitting into vitals and labs would invent a structure the data
 * does not support — the categorised ones are tagged instead.
 *
 * Values are right-aligned into a single column. A clinician scans this section for
 * numbers, so the numbers get a consistent position rather than trailing whatever
 * length the source's display name happens to be. */
export function ObservationsPanel({ data }: { data: SectionData<ObservationSummary> }) {
  return (
    <Section title="Observations" state={data.state} noun="observation" withheldCount={data.withheldCount} count={data.items.length}>
      {data.items.map((observation) => (
        <Row key={observation.id}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 items-baseline gap-2">
                <ConceptLabel concept={observation.concept} />
                {observation.isVitalSign && (
                  <span className="shrink-0 whitespace-nowrap rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
                    Vital sign
                  </span>
                )}
              </div>
              {observation.effective && (
                <p className="text-xs text-slate-500">
                  {observation.effective.display}
                  {observation.recency && ` · ${observation.recency.display}`}
                </p>
              )}
              {observation.value && observation.value.components.length > 0 && (
                <div className="mt-0.5 flex flex-wrap gap-x-4 text-xs text-slate-500">
                  {observation.value.components.map((component) => (
                    <span key={component.label.display ?? component.display}>
                      {component.label.display ?? "component"}:{" "}
                      <span className="tabular-nums">{component.display}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="shrink-0 text-right">
              <span
                className={`text-lg font-semibold tabular-nums ${
                  observation.value ? "text-slate-900" : "text-sm font-normal italic text-slate-500"
                }`}
              >
                {observation.value?.display ?? "No value recorded"}
              </span>
            </div>
          </div>

          <FlagList flags={observation.flags} />
        </Row>
      ))}
    </Section>
  );
}
