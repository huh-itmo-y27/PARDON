"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  getAvailableModels,
  getDatasetRecords,
  getDatasetSources,
  getExperiments,
  runPredict,
  type PredictRecord,
} from "../app/api";

const DEFAULT_FEATURES = {
  Accelerometer1RMS: 0.1,
  Accelerometer2RMS: 0.12,
  Current: 2.1,
  Pressure: 1.4,
  Temperature: 40,
  Thermocouple: 38.5,
  Voltage: 220,
  "Volume Flow RateRMS": 0.35,
};

export function InferencePanel() {
  const [mode, setMode] = useState<"manual" | "csv" | "dataset">("manual");
  const [models, setModels] = useState<string[]>(["isolation_forest"]);
  const [modelName, setModelName] = useState("isolation_forest");
  const [sourceId, setSourceId] = useState("ui-manual");
  const [featuresText, setFeaturesText] = useState(
    JSON.stringify(DEFAULT_FEATURES, null, 2)
  );
  const [csvName, setCsvName] = useState("");
  const [csvRecords, setCsvRecords] = useState<PredictRecord[]>([]);
  const [datasetSplit, setDatasetSplit] = useState<"train" | "val" | "test">("val");
  const [datasetSources, setDatasetSources] = useState<
    { source_id: string; rows_count: number }[]
  >([]);
  const [selectedDatasetSource, setSelectedDatasetSource] = useState("");
  const [datasetLimit, setDatasetLimit] = useState(50);
  const [datasetRecords, setDatasetRecords] = useState<PredictRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    requestId: string;
    recordsCount: number;
    anomaliesCount: number;
    avgScore: number;
    drift: unknown;
  } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const available = await getAvailableModels();
        const fromModels = available.map((x) => x.model_name).filter(Boolean);
        const fromExperiments = (await getExperiments(200))
          .map((x) => x.model_name)
          .filter(Boolean);
        const merged = Array.from(new Set([...fromModels, ...fromExperiments]));
        if (merged.length > 0) {
          setModels(merged);
          if (!merged.includes(modelName)) {
            setModelName(merged[0]);
          }
        }
      } catch {
        // Keep defaults when API bootstrap fails.
      }
    };
    void load();
  }, [modelName]);

  useEffect(() => {
    const loadSources = async () => {
      try {
        const rows = await getDatasetSources(datasetSplit);
        const mapped = rows.map((x) => ({
          source_id: x.source_id,
          rows_count: x.rows_count,
        }));
        setDatasetSources(mapped);
        if (mapped.length > 0 && !mapped.some((x) => x.source_id === selectedDatasetSource)) {
          setSelectedDatasetSource(mapped[0].source_id);
        }
      } catch {
        setDatasetSources([]);
      }
    };
    void loadSources();
  }, [datasetSplit, selectedDatasetSource]);

  const driftPretty = useMemo(
    () => (result ? JSON.stringify(result.drift, null, 2) : ""),
    [result]
  );

  const parseCsvText = (text: string): PredictRecord[] => {
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (lines.length < 2) return [];
    const delimiter = lines[0].includes(";") ? ";" : ",";
    const headers = lines[0].split(delimiter).map((h) => h.trim());
    const sourceIdx = headers.findIndex((h) => h === "source_id");
    const featureHeaders = headers.filter((h, idx) => idx !== sourceIdx);
    return lines.slice(1).map((line, rowIdx) => {
      const cols = line.split(delimiter).map((c) => c.trim());
      const source =
        sourceIdx >= 0 && cols[sourceIdx]
          ? cols[sourceIdx]
          : `${csvName || "csv"}:${rowIdx}`;
      const features: Record<string, number> = {};
      featureHeaders.forEach((name) => {
        const idx = headers.indexOf(name);
        const value = Number(cols[idx]);
        features[name] = Number.isFinite(value) ? value : 0;
      });
      return { source_id: source, features };
    });
  };

  const onCsvSelected = async (file: File | null) => {
    if (!file) return;
    setCsvName(file.name);
    const text = await file.text();
    const parsed = parseCsvText(text);
    setCsvRecords(parsed);
  };

  const onLoadDataset = async () => {
    if (!selectedDatasetSource) return;
    setLoading(true);
    setError("");
    try {
      const records = await getDatasetRecords(
        datasetSplit,
        selectedDatasetSource,
        datasetLimit,
        0
      );
      setDatasetRecords(records);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dataset rows");
      setDatasetRecords([]);
    } finally {
      setLoading(false);
    }
  };

  const onRun = async () => {
    setLoading(true);
    setError("");
    try {
      let records: PredictRecord[] = [];
      if (mode === "manual") {
        const parsed = JSON.parse(featuresText) as Record<string, number>;
        records = [{ source_id: sourceId || null, features: parsed }];
      } else if (mode === "csv") {
        records = csvRecords;
      } else {
        records = datasetRecords;
      }
      if (records.length === 0) {
        throw new Error("No records to run. Provide JSON, upload CSV, or load dataset.");
      }
      const response = await runPredict({
        model_name: modelName,
        records,
      });
      const scores = response.predictions.map((x) => x.score);
      const anomalies = response.predictions.filter((x) => x.anomaly_flag === 1).length;
      setResult({
        requestId: response.request_id,
        recordsCount: response.predictions.length,
        anomaliesCount: anomalies,
        avgScore:
          scores.length > 0
            ? scores.reduce((acc, value) => acc + value, 0) / scores.length
            : 0,
        drift: response.drift,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run predict");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section style={{ border: "1px solid #1e293b", padding: 12, borderRadius: 8 }}>
      <h3>Run Inference</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <button type="button" onClick={() => setMode("manual")} disabled={mode === "manual"}>
          Manual JSON
        </button>
        <button type="button" onClick={() => setMode("csv")} disabled={mode === "csv"}>
          Upload CSV
        </button>
        <button
          type="button"
          onClick={() => setMode("dataset")}
          disabled={mode === "dataset"}
        >
          Existing dataset
        </button>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <select value={modelName} onChange={(e) => setModelName(e.target.value)}>
          {models.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <button onClick={onRun} disabled={loading}>
          {loading ? "Running..." : "Predict"}
        </button>
      </div>
      {mode === "manual" ? (
        <div style={{ marginBottom: 8 }}>
          <input
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            placeholder="source_id"
            style={{ marginBottom: 8 }}
          />
          <div>Features JSON</div>
          <textarea
            value={featuresText}
            onChange={(e) => setFeaturesText(e.target.value)}
            rows={10}
            style={{ width: "100%", fontFamily: "monospace" }}
          />
        </div>
      ) : null}
      {mode === "csv" ? (
        <div style={{ marginBottom: 8 }}>
          <div>CSV format: include numeric feature columns, optional `source_id` column.</div>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => void onCsvSelected(e.target.files?.[0] ?? null)}
          />
          <div>Loaded rows: {csvRecords.length}</div>
        </div>
      ) : null}
      {mode === "dataset" ? (
        <div style={{ marginBottom: 8, display: "flex", gap: 8, alignItems: "center" }}>
          <select
            value={datasetSplit}
            onChange={(e) => setDatasetSplit(e.target.value as "train" | "val" | "test")}
          >
            <option value="train">train</option>
            <option value="val">val</option>
            <option value="test">test</option>
          </select>
          <select
            value={selectedDatasetSource}
            onChange={(e) => setSelectedDatasetSource(e.target.value)}
          >
            {datasetSources.map((source) => (
              <option key={source.source_id} value={source.source_id}>
                {source.source_id} ({source.rows_count})
              </option>
            ))}
          </select>
          <input
            type="number"
            min={1}
            max={2000}
            value={datasetLimit}
            onChange={(e) => setDatasetLimit(Math.max(1, Number(e.target.value) || 1))}
            style={{ width: 90 }}
          />
          <button type="button" onClick={onLoadDataset} disabled={loading || !selectedDatasetSource}>
            Load rows
          </button>
          <span>Loaded rows: {datasetRecords.length}</span>
        </div>
      ) : null}
      {result ? (
        <div>
          <div>
            Request ID: <code>{result.requestId}</code>
          </div>
          <div>
            Rows={result.recordsCount}, anomalies={result.anomaliesCount}, avg score=
            {result.avgScore.toFixed(4)}
          </div>
          <p style={{ marginTop: 6, marginBottom: 6 }}>
            <Link href={`/predictions/runs/${result.requestId}`}>
              Open full run metrics
            </Link>
          </p>
          <pre style={{ maxHeight: 220, overflowY: "auto" }}>{driftPretty}</pre>
        </div>
      ) : null}
      {error ? <pre>{error}</pre> : null}
    </section>
  );
}
