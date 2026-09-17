import { getPatientSummary } from "@/lib/api";
import { AllergiesList } from "@/components/AllergiesList";
import { DataQualityPanel } from "@/components/DataQualityPanel";
import { DemographicsHeader } from "@/components/DemographicsHeader";
import { EncountersList } from "@/components/EncountersList";
import { MedicationsList } from "@/components/MedicationsList";
import { ObservationsPanel } from "@/components/ObservationsPanel";
import { ProblemsList } from "@/components/ProblemsList";

// Rendered per request. Without this the fetch runs once during `next build` and
// the summary is frozen at build time — including the error state, if the API
// happened to be down.
export const dynamic = "force-dynamic";

export default async function Home() {
  const result = await getPatientSummary();

  if (!result.ok) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16">
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3">
          <h1 className="text-base font-semibold text-red-900">Clinical snapshot unavailable</h1>
          <p className="mt-1 text-sm text-red-800">{result.error}</p>
          <p className="mt-3 text-sm text-red-800">
            No patient data is shown because none could be retrieved. This is not an empty record.
          </p>
        </div>
      </main>
    );
  }

  const summary = result.summary;

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <div className="space-y-4">
        <DemographicsHeader patient={summary.patient} asOf={summary.asOf.display} />

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-4">
            <AllergiesList data={summary.allergies} />
            <ProblemsList data={summary.problems} />
            <MedicationsList data={summary.medications} />
          </div>
          <div className="space-y-4">
            <ObservationsPanel data={summary.observations} />
            <EncountersList data={summary.encounters} />
            <DataQualityPanel data={summary.dataQuality} />
          </div>
        </div>

        <p className="px-1 pb-4 text-xs text-slate-500">
          All dates and ages are relative to the bundle timestamp ({summary.asOf.display}), not to today.
        </p>
      </div>
    </main>
  );
}
