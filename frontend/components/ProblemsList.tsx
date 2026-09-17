import type { Problem, Section as SectionData } from "@/lib/types";
import { ConceptLabel } from "./ui/ConceptLabel";
import { FlagList } from "./ui/Badge";
import { Row, Section } from "./ui/Section";

export function ProblemsList({ data }: { data: SectionData<Problem> }) {
  const active = data.items.filter((p) => !p.isHistorical);
  const historical = data.items.filter((p) => p.isHistorical);

  return (
    <Section title="Problems" state={data.state} noun="condition" withheldCount={data.withheldCount} count={data.items.length}>
      {active.map((problem) => (
        <Row key={problem.id}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <ConceptLabel concept={problem.concept} />
            {problem.onset && <span className="text-xs text-slate-500">onset {problem.onset.display}</span>}
          </div>
          <FlagList flags={problem.flags} />
        </Row>
      ))}

      {historical.length > 0 && (
        <details className="mt-2 border-t border-slate-100 pt-2">
          <summary className="cursor-pointer text-xs text-slate-500">
            {historical.length} inactive or resolved
          </summary>
          {historical.map((problem) => (
            <Row key={problem.id}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-slate-600">
                  <ConceptLabel concept={problem.concept} />
                </span>
                <span className="text-xs text-slate-500">{problem.clinicalStatus}</span>
              </div>
              <FlagList flags={problem.flags} />
            </Row>
          ))}
        </details>
      )}
    </Section>
  );
}
