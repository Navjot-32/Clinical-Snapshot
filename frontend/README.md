# Frontend

A single server-rendered page that consumes `GET /patient-summary`. See the
[root README](../README.md) for setup and the reasoning behind the data decisions.

## Structure

```
app/page.tsx              the snapshot — fetches once, server-side
components/               one component per clinical section
components/ui/Section     owns the empty-state distinction
components/ui/Badge       the uncertainty flag vocabulary
components/ui/ConceptLabel renders a code honestly when it has no display name
lib/types.ts              hand-written mirror of the API response
lib/api.ts                fetch wrapper; returns a result rather than throwing
```

## Notes

- **No client components.** Expandable areas use native `<details>`, so the page
  ships no interactive JavaScript of its own.
- **`export const dynamic = "force-dynamic"`** in `page.tsx`. Without it Next
  prerenders at build time and freezes the summary — including the error state if
  the API happened to be down during the build.
- **No date parsing here.** The backend sends display strings with their precision
  attached. `new Date("2019")` would silently become 1 January 2019, inventing
  precision the source never claimed.
- **`BACKEND_URL`** overrides the API location (default `http://127.0.0.1:8000`).

## Commands

```bash
npm run dev     # development
npm run build   # production build
npx tsc --noEmit
```
