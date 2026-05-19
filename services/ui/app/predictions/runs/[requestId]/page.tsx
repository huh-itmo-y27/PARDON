import Link from "next/link";

import { getPredictionRunDetail } from "../../../api";
import { PredictionRunChart } from "../../../../components/PredictionRunChart";

export default async function PredictionRunDetailsPage({
  params,
}: {
  params: { requestId: string };
}) {
  const run = await getPredictionRunDetail(params.requestId);
  return (
    <>
      <p>
        <Link href="/predictions">Back to prediction runs</Link>
      </p>
      <h1>Prediction Run Details</h1>
      <p>
        <b>Request ID:</b> {run.request_id}
      </p>
      <p>
        <b>Model:</b> {run.model_name}
      </p>
      <p>
        <b>Created:</b> {new Date(run.created_at).toLocaleString()}
      </p>
      <p>
        <b>Rows:</b> {run.records_count}, <b>Anomalies:</b> {run.anomalies_count},{" "}
        <b>Anomaly rate:</b> {(run.anomaly_rate * 100).toFixed(1)}%, <b>Avg score:</b>{" "}
        {run.avg_score.toFixed(4)}, <b>Max score:</b> {run.max_score.toFixed(4)}
      </p>
      <PredictionRunChart rows={run.rows} />

      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Source</th>
            <th>Score</th>
            <th>Threshold</th>
            <th>Flag</th>
          </tr>
        </thead>
        <tbody>
          {run.rows.map((row) => (
            <tr key={row.id}>
              <td>{new Date(row.created_at).toLocaleString()}</td>
              <td>{row.source_id || "-"}</td>
              <td>{row.score.toFixed(4)}</td>
              <td>{row.threshold.toFixed(4)}</td>
              <td>{row.anomaly_flag}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
