import type { CodedConcept } from "@/lib/types";

/** Shows what the source actually said. When no display name was provided we show
 * the code and its system rather than inventing a clinical name for it.
 *
 * Long names are clamped so rows stay a uniform height and the column scans; the
 * full string stays in `title` so nothing is actually hidden. Source display text
 * is never edited — LOINC's "...with all children optional" is verbose, but
 * trimming it would be rewriting the record. */
export function ConceptLabel({ concept }: { concept: CodedConcept }) {
  const code = concept.code && (
    <span className="ml-1.5 whitespace-nowrap font-normal text-xs text-slate-400">
      {concept.systemLabel} {concept.code}
    </span>
  );

  if (concept.hasDisplay && concept.display) {
    return (
      <span className="min-w-0 font-medium text-slate-900" title={concept.display}>
        <span className="line-clamp-1">
          {concept.display}
          {code}
        </span>
      </span>
    );
  }

  if (concept.code) {
    return (
      <span className="font-medium text-slate-900">
        <span className="font-mono">{concept.code}</span>
        <span className="ml-1.5 whitespace-nowrap font-normal text-xs text-slate-500">
          {concept.systemLabel ?? "unknown system"}
        </span>
      </span>
    );
  }

  return <span className="font-medium italic text-slate-500">Not coded in source</span>;
}
