import type { Medication, MedicationSection } from "@/lib/types";
import { ConceptLabel } from "./ui/ConceptLabel";
import { FlagList } from "./ui/Badge";
import { Row, Section } from "./ui/Section";

function MedicationRow({ medication }: { medication: Medication }) {
  return (
    <Row>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <ConceptLabel concept={medication.concept} />
        {medication.authoredOn && (
          <span className="text-xs text-slate-500">authored {medication.authoredOn.display}</span>
        )}
      </div>
      {medication.dosage && <p className="text-[13px] text-slate-600">{medication.dosage}</p>}
      <FlagList flags={medication.flags} />
    </Row>
  );
}

export function MedicationsList({ data }: { data: MedicationSection }) {
  const count = data.active.length + data.historical.length + data.unverifiedSubject.length;

  return (
    <Section title="Medications" state={data.state} noun="medication" withheldCount={data.withheldCount} count={count}>
      {data.active.length > 0 ? (
        data.active.map((medication) => <MedicationRow key={medication.id} medication={medication} />)
      ) : (
        <p className="py-1 text-sm text-slate-500">No active medications.</p>
      )}

      {/* Kept out of the active list on purpose. These were prescribed against a
          patient record we matched but did not confirm, and presenting them as
          this patient's current medication would be asserting more than we know. */}
      {data.unverifiedSubject.length > 0 && (
        <div className="mt-3 rounded border border-amber-300 bg-amber-50 px-3 py-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">
            From a possible duplicate record — identity not verified
          </p>
          <p className="mb-1 text-[12px] text-amber-800">
            Prescribed against {data.unverifiedSubject[0].sourceRecord ?? "another patient record"} which was matched to
            this patient but not confirmed. Verify before acting on it.
          </p>
          {data.unverifiedSubject.map((medication) => (
            <MedicationRow key={medication.id} medication={medication} />
          ))}
        </div>
      )}

      {data.historical.length > 0 && (
        <details className="mt-2 border-t border-slate-100 pt-2">
          <summary className="cursor-pointer text-xs text-slate-500">
            {data.historical.length} stopped or completed
          </summary>
          {data.historical.map((medication) => (
            <MedicationRow key={medication.id} medication={medication} />
          ))}
        </details>
      )}
    </Section>
  );
}
