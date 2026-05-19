"use client";

import { useEffect, useRef, useState } from "react";

import {
  getActiveRetrain,
  getExperiments,
  getRetrainStatus,
  startRetrain,
} from "../app/api";

export function RetrainPanel() {
  const [modelName, setModelName] = useState("isolation_forest");
  const [datasetScenario, setDatasetScenario] = useState("all");
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("");
  const [details, setDetails] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);
  const [modelOptions, setModelOptions] = useState<string[]>([
    "isolation_forest",
    "conv_ae",
    "lstm_ae",
  ]);
  const [scenarioOptions, setScenarioOptions] = useState<string[]>(["all"]);

  useEffect(() => {
    const restoreActive = async () => {
      try {
        const experiments = await getExperiments(200);
        const models = Array.from(
          new Set(
            experiments.map((x) => x.model_name).filter((x) => x && x.length > 0)
          )
        );
        if (models.length > 0) {
          setModelOptions(models);
          if (!models.includes(modelName)) {
            setModelName(models[0]);
          }
        }
        const scenarios = Array.from(
          new Set(
            experiments
              .map((x) => x.params?.dataset_scenario)
              .filter((x): x is string => Boolean(x))
          )
        );
        if (scenarios.length > 0) {
          setScenarioOptions(scenarios);
          if (!scenarios.includes(datasetScenario)) {
            setDatasetScenario(scenarios[0]);
          }
        }

        const active = await getActiveRetrain();
        if (!active) return;
        setJobId(active.job_id);
        setStatus(active.status);
        setDetails(active.details || {});
        setModelName(active.model_name);
        setDatasetScenario(active.dataset_scenario);
      } catch {
        // Ignore initial hydration fetch errors.
      }
    };
    void restoreActive();
  }, []);

  const onRetrain = async () => {
    if (!window.confirm("Start retraining now?")) return;
    setLoading(true);
    setError("");
    try {
      const job = await startRetrain(modelName, datasetScenario);
      setJobId(job.job_id);
      setStatus(job.status);
      setDetails(job.details || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start retrain");
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    if (!jobId) return;
    setLoading(true);
    setError("");
    try {
      const job = await getRetrainStatus(jobId);
      setStatus(job.status);
      setDetails(job.details || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh job");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!jobId || !["queued", "running"].includes(status)) {
      return;
    }
    const timer = setInterval(() => {
      void (async () => {
        try {
          const job = await getRetrainStatus(jobId);
          setStatus(job.status);
          setDetails(job.details || {});
        } catch {
          // Keep previous state if a poll fails.
        }
      })();
    }, 2000);
    return () => clearInterval(timer);
  }, [jobId, status]);

  const statusMessage =
    typeof details.message === "string" ? details.message : "No status message yet.";
  const stdoutTail = typeof details.stdout === "string" ? details.stdout : "";
  const stderrTail = typeof details.stderr === "string" ? details.stderr : "";
  const stdoutRef = useRef<HTMLPreElement | null>(null);
  const stderrRef = useRef<HTMLPreElement | null>(null);
  const scrollToBottom = (el: HTMLPreElement | null) => {
    if (!el) {
      return;
    }
    el.scrollTop = el.scrollHeight;
  };

  useEffect(() => {
    if (!autoScrollLogs) {
      return;
    }
    scrollToBottom(stdoutRef.current);
    scrollToBottom(stderrRef.current);
  }, [autoScrollLogs, stdoutTail, stderrTail]);

  return (
    <section style={{ border: "1px solid #1e293b", padding: 12, borderRadius: 8 }}>
      <h3>Retrain</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <select value={modelName} onChange={(e) => setModelName(e.target.value)}>
          {modelOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <select
          value={datasetScenario}
          onChange={(e) => setDatasetScenario(e.target.value)}
        >
          {scenarioOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <button onClick={onRetrain} disabled={loading}>Retrain</button>
        <button onClick={onRefresh} disabled={loading || !jobId}>Refresh status</button>
      </div>
      <div>Job ID: {jobId || "n/a"}</div>
      <div>Status: {status || "n/a"}</div>
      <div>Status message: {statusMessage}</div>
      <label style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <input
          type="checkbox"
          checked={autoScrollLogs}
          onChange={(e) => setAutoScrollLogs(e.target.checked)}
        />
        Auto-scroll logs
      </label>
      {stdoutTail ? (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span>Stdout (tail)</span>
            <button type="button" onClick={() => scrollToBottom(stdoutRef.current)}>
              Jump to latest
            </button>
          </div>
          <pre ref={stdoutRef} style={{ maxHeight: 180, overflowY: "auto" }}>
            {stdoutTail}
          </pre>
        </>
      ) : null}
      {stderrTail ? (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span>Stderr (tail)</span>
            <button type="button" onClick={() => scrollToBottom(stderrRef.current)}>
              Jump to latest
            </button>
          </div>
          <pre ref={stderrRef} style={{ maxHeight: 180, overflowY: "auto" }}>
            {stderrTail}
          </pre>
        </>
      ) : null}
      {error ? <pre>{error}</pre> : null}
    </section>
  );
}

