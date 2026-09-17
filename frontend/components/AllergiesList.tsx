import type { Allergy, Section as SectionData } from "@/lib/types";
import { ConceptLabel } from "./ui/ConceptLabel";
import { FlagList } from "./ui/Badge";
import { Row, Section } from "./ui/Section";

export function AllergiesList({ data }: { data: SectionData<Allergy> }) {
  return (
    <Section title="Allergies" state={data.state} noun="allergy" withheldCount={data.withheldCount} count={data.items.length}>
      {data.items.map((allergy) => (
        <Row key={allergy.id}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <ConceptLabel concept={allergy.concept} />
            <div className="flex items-baseline gap-2 text-xs">
              {allergy.criticality === "high" && (
                <span
                  aria-label="Criticality: high"
                  className="rounded bg-red-100 px-1.5 py-0.5 font-semibold text-red-800 ring-1 ring-inset ring-red-300"
                >
                  High criticality
                </span>
              )}
              {allergy.criticality === "unable-to-assess" && (
                <span className="text-slate-500">Criticality not assessable</span>
              )}
              {allergy.recordedDate && <span className="text-slate-500">recorded {allergy.recordedDate.display}</span>}
            </div>
          </div>
          <FlagList flags={allergy.flags} />
        </Row>
      ))}
    </Section>
  );
}
