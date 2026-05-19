import Link from "next/link";

import { getExperimentByRunId } from "../../api";

type KV = Record<string, string | number>;

function KeyValueTable({ title, data }: { title: string; data: KV }) {
  const entries = Object.entries(data).sort(([a], [b]) => a.localeCompare(b));
  return (
    <section style={{ marginBottom: 16 }}>
      <h3>{title}</h3>
      {entries.length === 0 ? (
        <p>No values.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Key</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td>{key}</td>
                <td>{String(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default async function ExperimentDetailsPage({
  params,
}: {
  params: { runId: string };
}) {
  const run = await getExperimentByRunId(params.runId);
  return (
    <>
      <p>
        <Link href="/experiments">Back to experiments</Link>
      </p>
      <h1>Experiment Run Details</h1>
      <p>
        <b>Run ID:</b> {run.run_id}
      </p>
      <p>
        <b>Experiment:</b> {run.experiment}
      </p>
      <p>
        <b>Model:</b> {run.model_name || "-"}
      </p>
      <p>
        <b>Status:</b> {run.status}
      </p>
      <p>
        <b>Started:</b>{" "}
        {run.started_at ? new Date(run.started_at).toLocaleString() : "-"}
      </p>

      <KeyValueTable title="Metrics" data={run.metrics} />
      <KeyValueTable title="Params" data={run.params} />
      <KeyValueTable title="Tags" data={run.tags} />
    </>
  );
}
