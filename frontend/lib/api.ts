import type { PatientSummary } from "./types";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export type SummaryResult =
  | { ok: true; summary: PatientSummary }
  | { ok: false; error: string };

export async function getPatientSummary(): Promise<SummaryResult> {
  // Next 16 does not cache fetch by default, so this is always current.
  try {
    const response = await fetch(`${BACKEND_URL}/patient-summary`);
    if (!response.ok) {
      return { ok: false, error: `The API responded with ${response.status} ${response.statusText}.` };
    }
    return { ok: true, summary: (await response.json()) as PatientSummary };
  } catch {
    return { ok: false, error: `Could not reach the API at ${BACKEND_URL}. Is the backend running?` };
  }
}
