import type { EncounterSummary, Section as SectionData } from "@/lib/types";
import { ConceptLabel } from "./ui/ConceptLabel";
import { FlagList } from "./ui/Badge";
import { Row, Section } from "./ui/Section";

export function EncountersList({ data }: { data: SectionData<EncounterSummary> }) {
  return (
    <Section title="Encounters" state={data.state} noun="encounter" withheldCount={data.withheldCount} count={data.items.length}>
      {data.items.map((encounter) => (
        <Row key={encounter.id}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              {encounter.type ? (
                <ConceptLabel concept={encounter.type} />
              ) : (
                <span className="font-medium italic text-slate-500">Encounter type not recorded</span>
              )}
              <p className="text-xs text-slate-500">
                {encounter.start?.display ?? "date unknown"}
                {encounter.recency && ` · ${encounter.recency.display}`}
              </p>
            </div>
            {encounter.classDisplay && (
              <span className="shrink-0 whitespace-nowrap rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
                {encounter.classDisplay}
              </span>
            )}
          </div>
          <FlagList flags={encounter.flags} />
        </Row>
      ))}
    </Section>
  );
}
