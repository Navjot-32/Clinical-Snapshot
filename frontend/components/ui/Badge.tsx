import type { Flag, FlagCode } from "@/lib/types";

// Wording is aimed at a clinician, not at whoever wrote the FHIR. Tone maps to how
// much the flag should change what the reader believes.
const LABELS: Record<FlagCode, { text: string; tone: "warn" | "info" | "muted" }> = {
  "unverified-subject": { text: "Identity not verified", tone: "warn" },
  "coding-mismatch": { text: "Coding mismatch", tone: "warn" },
  unconfirmed: { text: "Unconfirmed", tone: "warn" },
  "unrecognised-status": { text: "Status unrecognised", tone: "warn" },
  stale: { text: "Out of date", tone: "info" },
  "unresolved-reference": { text: "Link unresolved", tone: "info" },
  "unmapped-code": { text: "No name in source", tone: "muted" },
  "low-precision-date": { text: "Approximate date", tone: "muted" },
};

const TONES = {
  warn: "bg-amber-50 text-amber-900 ring-amber-300",
  info: "bg-sky-50 text-sky-900 ring-sky-300",
  muted: "bg-slate-100 text-slate-700 ring-slate-300",
} as const;

export function Badge({ flag }: { flag: Flag }) {
  const label = LABELS[flag.code] ?? { text: flag.code, tone: "muted" as const };
  return (
    <span
      title={flag.detail ?? undefined}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${TONES[label.tone]}`}
    >
      {label.text}
    </span>
  );
}

export function FlagList({ flags }: { flags: Flag[] }) {
  if (flags.length === 0) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {flags.map((flag, index) => (
        <Badge key={`${flag.code}-${index}`} flag={flag} />
      ))}
    </div>
  );
}
