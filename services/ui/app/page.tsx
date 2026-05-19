import Link from "next/link";

import { getNotifications, getRecentPredictions } from "./api";
import { InferencePanel } from "../components/InferencePanel";
import { RetrainPanel } from "../components/RetrainPanel";

export default async function DashboardPage() {
  const [predictions, notifications] = await Promise.all([
    getRecentPredictions(10),
    getNotifications(5),
  ]);
  const anomalyCount = predictions.filter((x) => x.anomaly_flag === 1).length;
  return (
    <>
      <h1>PARDON Interface</h1>
      <p>Operational entry page for inference experiments and drift-aware retraining.</p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
        <div style={{ border: "1px solid #1e293b", padding: 12, borderRadius: 8 }}>
          <strong>Recent predictions</strong>
          <div>{predictions.length}</div>
        </div>
        <div style={{ border: "1px solid #1e293b", padding: 12, borderRadius: 8 }}>
          <strong>Anomaly flags</strong>
          <div>{anomalyCount}</div>
        </div>
        <div style={{ border: "1px solid #1e293b", padding: 12, borderRadius: 8 }}>
          <strong>Drift alerts</strong>
          <div>{notifications.length}</div>
        </div>
      </div>
      <InferencePanel />
      <div style={{ height: 12 }} />
      <RetrainPanel />
      <p style={{ marginTop: 16 }}>
        <Link href="/predictions">Open recent predictions table</Link>
      </p>
    </>
  );
}

