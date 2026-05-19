import Link from "next/link";

import { getExperiments } from "../api";

export default async function ExperimentsPage({
  searchParams,
}: {
  searchParams?: { model?: string; page?: string; limit?: string };
}) {
  const pageRaw = Number(searchParams?.page ?? "0");
  const limitRaw = Number(searchParams?.limit ?? "30");
  const page = Number.isFinite(pageRaw) && pageRaw >= 0 ? Math.floor(pageRaw) : 0;
  const limit =
    Number.isFinite(limitRaw) && limitRaw >= 1 && limitRaw <= 200
      ? Math.floor(limitRaw)
      : 30;
  const offset = page * limit;
  const rows = await getExperiments(limit, searchParams?.model, offset);

  const prevParams = new URLSearchParams();
  if (searchParams?.model) prevParams.set("model", searchParams.model);
  prevParams.set("page", String(Math.max(0, page - 1)));
  prevParams.set("limit", String(limit));
  const nextParams = new URLSearchParams();
  if (searchParams?.model) nextParams.set("model", searchParams.model);
  nextParams.set("page", String(page + 1));
  nextParams.set("limit", String(limit));
  return (
    <>
      <h1>Experiments</h1>
      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        {page > 0 ? (
          <Link href={`/experiments?${prevParams.toString()}`} aria-label="Previous page">
            ← Prev {limit}
          </Link>
        ) : (
          <span style={{ opacity: 0.5 }}>← Prev {limit}</span>
        )}
        <span>Page {page + 1}</span>
        {rows.length === limit ? (
          <Link href={`/experiments?${nextParams.toString()}`} aria-label="Next page">
            Next {limit} →
          </Link>
        ) : (
          <span style={{ opacity: 0.5 }}>Next {limit} →</span>
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>Started</th>
            <th>Experiment</th>
            <th>Model</th>
            <th>Status</th>
            <th>Run ID</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.run_id}>
              <td>{row.started_at ? new Date(row.started_at).toLocaleString() : "-"}</td>
              <td>{row.experiment}</td>
              <td>{row.model_name || "-"}</td>
              <td>{row.status}</td>
              <td>
                <Link href={`/experiments/${row.run_id}`}>
                  {row.run_id.slice(0, 12)}...
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

