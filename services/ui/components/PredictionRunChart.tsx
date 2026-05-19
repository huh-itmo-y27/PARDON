"use client";

import { useMemo, useState } from "react";

type Row = {
  id: number;
  created_at: string;
  source_id: string | null;
  score: number;
  anomaly_flag: number;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function PredictionRunChart({ rows }: { rows: Row[] }) {
  const sorted = useMemo(
    () =>
      [...rows].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      ),
    [rows]
  );
  const [startPct, setStartPct] = useState(0);
  const [endPct, setEndPct] = useState(100);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const chartWidth = 860;
  const chartHeight = 300;
  const padX = 40;
  const padY = 16;

  const startIdx = Math.floor((startPct / 100) * (sorted.length - 1));
  const endIdx = Math.max(
    startIdx + 1,
    Math.ceil((endPct / 100) * (sorted.length - 1))
  );
  const visible = sorted.slice(startIdx, endIdx + 1);

  const yMin = useMemo(
    () => Math.min(...visible.map((x) => x.score), 0),
    [visible]
  );
  const yMax = useMemo(
    () => Math.max(...visible.map((x) => x.score), 1),
    [visible]
  );
  const yRange = Math.max(yMax - yMin, 1e-9);

  const points = visible.map((item, i) => {
    const x =
      padX +
      (i / Math.max(visible.length - 1, 1)) * (chartWidth - 2 * padX);
    const y =
      chartHeight - padY - ((item.score - yMin) / yRange) * (chartHeight - 2 * padY);
    return { ...item, x, y };
  });

  const polyline = points.map((p) => `${p.x},${p.y}`).join(" ");

  const hoveredPoint =
    hoveredIdx !== null && hoveredIdx >= 0 && hoveredIdx < points.length
      ? points[hoveredIdx]
      : null;

  return (
    <section style={{ border: "1px solid #1e293b", borderRadius: 8, padding: 12 }}>
      <h3>Score time series</h3>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 10 }}>
        <label>
          Start %
          <input
            type="range"
            min={0}
            max={99}
            value={startPct}
            onChange={(e) => {
              const value = Number(e.target.value);
              setStartPct(clamp(value, 0, endPct - 1));
            }}
          />
          <span>{startPct}</span>
        </label>
        <label>
          End %
          <input
            type="range"
            min={1}
            max={100}
            value={endPct}
            onChange={(e) => {
              const value = Number(e.target.value);
              setEndPct(clamp(value, startPct + 1, 100));
            }}
          />
          <span>{endPct}</span>
        </label>
        <span>
          Showing {visible.length} points ({startIdx + 1}..{endIdx + 1})
        </span>
      </div>

      <div style={{ overflowX: "auto" }}>
        <svg
          width={chartWidth}
          height={chartHeight}
          role="img"
          aria-label="Prediction score time series"
          onMouseLeave={() => setHoveredIdx(null)}
        >
          <rect x={0} y={0} width={chartWidth} height={chartHeight} fill="transparent" />
          <line
            x1={padX}
            y1={chartHeight - padY}
            x2={chartWidth - padX}
            y2={chartHeight - padY}
            stroke="#334155"
          />
          <line
            x1={padX}
            y1={padY}
            x2={padX}
            y2={chartHeight - padY}
            stroke="#334155"
          />

          {points.length > 1 ? (
            <polyline
              fill="none"
              stroke="#60a5fa"
              strokeWidth="2"
              points={polyline}
            />
          ) : null}

          {points.map((p, idx) => (
            <circle
              key={p.id}
              cx={p.x}
              cy={p.y}
              r={p.anomaly_flag === 1 ? 4 : 2.5}
              fill={p.anomaly_flag === 1 ? "#ef4444" : "#93c5fd"}
              opacity={hoveredIdx === idx ? 1 : 0.9}
              onMouseEnter={() => setHoveredIdx(idx)}
            />
          ))}

          {hoveredPoint ? (
            <>
              <line
                x1={hoveredPoint.x}
                y1={padY}
                x2={hoveredPoint.x}
                y2={chartHeight - padY}
                stroke="#64748b"
                strokeDasharray="4,4"
              />
              <rect
                x={clamp(hoveredPoint.x + 8, 8, chartWidth - 250)}
                y={padY + 4}
                width={240}
                height={76}
                fill="#0f172a"
                stroke="#334155"
                rx={6}
              />
              <text
                x={clamp(hoveredPoint.x + 16, 16, chartWidth - 242)}
                y={padY + 22}
                fill="#e2e8f0"
                fontSize={12}
              >
                {new Date(hoveredPoint.created_at).toLocaleString()}
              </text>
              <text
                x={clamp(hoveredPoint.x + 16, 16, chartWidth - 242)}
                y={padY + 40}
                fill="#e2e8f0"
                fontSize={12}
              >
                score={hoveredPoint.score.toFixed(4)}
              </text>
              <text
                x={clamp(hoveredPoint.x + 16, 16, chartWidth - 242)}
                y={padY + 58}
                fill={hoveredPoint.anomaly_flag === 1 ? "#ef4444" : "#93c5fd"}
                fontSize={12}
              >
                anomaly={hoveredPoint.anomaly_flag} source={hoveredPoint.source_id || "-"}
              </text>
            </>
          ) : null}
        </svg>
      </div>
      <p style={{ marginTop: 6, opacity: 0.8 }}>
        Red points are anomalies. Hover points for exact values.
      </p>
    </section>
  );
}
