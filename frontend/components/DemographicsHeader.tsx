import type { Demographics, Sourced } from "@/lib/types";

function sourceLabels(patient: Demographics, sources: string[]): string {
  const byId = new Map(patient.identity.sourceRecords.map((r) => [r.id, r.mrn ?? r.id]));
  return sources.map((id) => byId.get(id) ?? id).join(", ");
}

/** Provenance is only worth showing where it tells the reader something: a value
 * that came from the unverified duplicate, not one both records agreed on. */
function Provenance({ patient, sources }: { patient: Demographics; sources: string[] }) {
  const primaryId = patient.identity.sourceRecords.find((r) => r.role === "primary")?.id;
  const onlyFromDuplicate = sources.length === 1 && sources[0] !== primaryId;
  if (!onlyFromDuplicate) return null;
  return <span className="ml-1.5 text-xs text-amber-800">from {sourceLabels(patient, sources)}</span>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-900">{children}</dd>
    </div>
  );
}

export function DemographicsHeader({ patient, asOf }: { patient: Demographics; asOf: string }) {
  const merged = patient.identity.resolution === "merged-probable-duplicate";

  return (
    <header className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">{patient.name?.value ?? "Unnamed patient"}</h1>
          <p className="text-sm text-slate-600">
            {[patient.age?.value, patient.gender?.value, patient.birthDate && `born ${patient.birthDate.value.display}`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <p className="text-xs text-slate-500">Snapshot as of {asOf}</p>
      </div>

      {merged && (
        <details className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          <summary className="cursor-pointer font-medium">
            Two patient records were combined — identity matched, not confirmed
          </summary>
          <div className="mt-2 space-y-2">
            <ul className="list-disc space-y-0.5 pl-5 text-[13px]">
              {patient.identity.matchEvidence.map((evidence) => (
                <li key={evidence}>{evidence}</li>
              ))}
            </ul>
            <p className="text-[13px]">
              Source records:{" "}
              {patient.identity.sourceRecords.map((r) => `${r.mrn ?? r.id} (${r.role})`).join(" · ")}
            </p>
          </div>
        </details>
      )}

      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 py-3 sm:grid-cols-4">
        <Field label="Identifiers">
          {patient.identifiers.map((id: Sourced<string>) => {
            const primaryId = patient.identity.sourceRecords.find((r) => r.role === "primary")?.id;
            const fromDuplicate = id.sources.length === 1 && id.sources[0] !== primaryId;
            return (
              <div key={id.value} className="text-[13px]">
                <span className="font-mono">{id.value}</span>
                {fromDuplicate && <span className="ml-1.5 text-xs text-amber-800">duplicate record</span>}
              </div>
            );
          })}
        </Field>

        <Field label="Contact">
          {patient.telecom.length === 0 ? (
            <span className="text-slate-500">None recorded</span>
          ) : (
            patient.telecom.map((contact) => (
              <div key={contact.value.value} className="text-[13px]">
                <span className="text-slate-500">{contact.value.use}</span> {contact.value.value}
                <Provenance patient={patient} sources={contact.sources} />
              </div>
            ))
          )}
        </Field>

        <Field label="Address">
          <span className="text-[13px]">{patient.address?.value ?? "None recorded"}</span>
        </Field>

        <Field label="Race / ethnicity">
          <span className="text-[13px]">
            {[patient.race?.value, patient.ethnicity?.value].filter(Boolean).join(" · ") || "Not recorded"}
          </span>
        </Field>
      </dl>

      {patient.birthDate?.note && (
        <p className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
          Date of birth: {patient.birthDate.note}
        </p>
      )}
    </header>
  );
}
