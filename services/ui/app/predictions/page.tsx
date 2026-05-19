import Link from "next/link";

import { getPredictionRuns } from "../api";

export default async function PredictionsPage({
  searchParams,
}: {
  searchParams?: { model?: string; page?: string; limit?: string };
}) {
  const pageRaw = Number(searchParams?.page ?? "0");
  const limitRaw = Number(searchParams?.limit ?? "50");
  const page = Number.isFinite(pageRaw) && pageRaw >= 0 ? Math.floor(pageRaw) : 0;
  const limit =
    Number.isFinite(limitRaw) && limitRaw >= 1 && limitRaw <= 200
      ? Math.floor(limitRaw)
      : 50;
  const offset = page * limit;
  const modelName = searchParams?.model;
  const rows = await getPredictionRuns(limit, modelName, offset);
  const prevParams = new URLSearchParams();
  const nextParams = new URLSearchParams();
  if (modelName) {
    prevParams.set("model", modelName);
    nextParams.set("model", modelName);
  }
  prevParams.set("page", String(Math.max(0, page - 1)));
  nextParams.set("page", String(page + 1));
  prevParams.set("limit", String(limit));
  nextParams.set("limit", String(limit));
  return (
    <>
      <h1>Prediction runs</h1>
      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        {page > 0 ? (
          <Link href={`/predictions?${prevParams.toString()}`} aria-label="Previous page">
            ← Prev {limit}
          </Link>
        ) : (
          <span style={{ opacity: 0.5 }}>← Prev {limit}</span>
        )}
        <span>Page {page + 1}</span>
        {rows.length === limit ? (
          <Link href={`/predictions?${nextParams.toString()}`} aria-label="Next page">
            Next {limit} →
          </Link>
        ) : (
          <span style={{ opacity: 0.5 }}>Next {limit} →</span>
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Model</th>
            <th>Request ID</th>
            <th>Rows</th>
            <th>Anomalies</th>
            <th>Anomaly rate</th>
            <th>Avg score</th>
            <th>Max score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.request_id}>
              <td>{new Date(row.created_at).toLocaleString()}</td>
              <td>{row.model_name}</td>
              <td>
                <Link href={`/predictions/runs/${row.request_id}`}>
                  {row.request_id.slice(0, 12)}...
                </Link>
              </td>
              <td>{row.records_count}</td>
              <td>{row.anomalies_count}</td>
              <td>{(row.anomaly_rate * 100).toFixed(1)}%</td>
              <td>{row.avg_score.toFixed(4)}</td>
              <td>{row.max_score.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

