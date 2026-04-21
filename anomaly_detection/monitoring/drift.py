from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

EPS = 1e-9


def _safe_float(value: float | int | np.floating) -> float:
    return float(value) if np.isfinite(value) else 0.0


def _psi_from_bins(
    expected_ratio: np.ndarray, actual: np.ndarray, edges: np.ndarray
) -> float:
    if actual.size == 0 or edges.size <= 1:
        return 0.0
    actual_hist, _ = np.histogram(actual, bins=edges)
    actual_ratio = actual_hist / max(actual_hist.sum(), 1)
    expected_ratio = np.clip(expected_ratio, EPS, None)
    actual_ratio = np.clip(actual_ratio, EPS, None)
    return _safe_float(
        np.sum(
            (actual_ratio - expected_ratio)
            * np.log(actual_ratio / expected_ratio)
        )
    )


def build_reference_profile(
    train_df: pd.DataFrame,
    feature_cols: list[str],
    label_cols: list[str],
) -> dict[str, Any]:
    feature_profile: dict[str, dict[str, float]] = {}
    for col in feature_cols:
        series = pd.to_numeric(train_df[col], errors="coerce").dropna()
        arr = series.to_numpy(dtype=float)
        if arr.size == 0:
            continue
        feature_profile[col] = {
            "mean": _safe_float(np.mean(arr)),
            "std": _safe_float(np.std(arr)),
            "min": _safe_float(np.min(arr)),
            "max": _safe_float(np.max(arr)),
            "p05": _safe_float(np.quantile(arr, 0.05)),
            "p50": _safe_float(np.quantile(arr, 0.50)),
            "p95": _safe_float(np.quantile(arr, 0.95)),
        }
        quantiles = np.linspace(0.0, 1.0, 11)
        edges = np.unique(np.quantile(arr, quantiles))
        if edges.size > 1:
            expected_hist, _ = np.histogram(arr, bins=edges)
            expected_ratio = expected_hist / max(expected_hist.sum(), 1)
            feature_profile[col]["psi_edges"] = edges.tolist()
            feature_profile[col]["psi_expected_ratio"] = expected_ratio.tolist()

    label_rates: dict[str, float] = {}
    for col in label_cols:
        if col in train_df.columns:
            label_rates[col] = _safe_float(
                pd.to_numeric(train_df[col], errors="coerce").fillna(0).mean()
            )

    return {
        "row_count": int(len(train_df)),
        "feature_columns": feature_cols,
        "feature_profile": feature_profile,
        "label_rates": label_rates,
    }


def compute_data_drift(
    current_df: pd.DataFrame, reference_profile: dict[str, Any]
) -> dict[str, Any]:
    features = reference_profile.get("feature_columns", [])
    feature_stats: dict[str, dict[str, float | bool]] = {}
    psi_values: list[float] = []
    ks_values: list[float] = []
    ref_stats = reference_profile.get("feature_profile", {})

    for feature in features:
        if feature not in current_df.columns or feature not in ref_stats:
            continue
        cur_series = pd.to_numeric(
            current_df[feature], errors="coerce"
        ).dropna()
        cur_arr = cur_series.to_numpy(dtype=float)
        if cur_arr.size == 0:
            continue

        ref_mean = float(ref_stats[feature].get("mean", 0.0))
        ref_std = max(float(ref_stats[feature].get("std", 0.0)), EPS)
        edges = np.array(ref_stats[feature].get("psi_edges", []), dtype=float)
        expected_ratio = np.array(
            ref_stats[feature].get("psi_expected_ratio", []), dtype=float
        )
        feature_psi = _psi_from_bins(expected_ratio, cur_arr, edges)
        z_shift = abs(_safe_float(np.mean(cur_arr)) - ref_mean) / ref_std
        p95 = float(ref_stats[feature].get("p95", np.max(cur_arr)))
        p05 = float(ref_stats[feature].get("p05", np.min(cur_arr)))
        out_of_band = np.mean((cur_arr < p05) | (cur_arr > p95))

        psi_values.append(feature_psi)
        ks_values.append(float(out_of_band))
        feature_stats[feature] = {
            "psi": feature_psi,
            "outside_reference_band_rate": _safe_float(out_of_band),
            "mean_shift_z": z_shift,
            "drift_detected": bool(feature_psi >= 0.2 or out_of_band >= 0.2),
        }

    drift_score = _safe_float(np.mean(psi_values)) if psi_values else 0.0
    ks_score = _safe_float(np.mean(ks_values)) if ks_values else 0.0
    return {
        "data_drift_score": drift_score,
        "data_drift_ks_score": ks_score,
        "drifted_feature_count": int(
            sum(
                1
                for stat in feature_stats.values()
                if bool(stat["drift_detected"])
            )
        ),
        "feature_stats": feature_stats,
    }


def compute_target_drift(
    current_labels: pd.DataFrame,
    reference_rates: dict[str, float],
) -> dict[str, Any]:
    per_label: dict[str, dict[str, float | bool]] = {}
    deltas: list[float] = []
    for label, ref_rate in reference_rates.items():
        if label not in current_labels.columns:
            continue
        current_rate = _safe_float(
            pd.to_numeric(current_labels[label], errors="coerce")
            .fillna(0)
            .mean()
        )
        delta = abs(current_rate - float(ref_rate))
        deltas.append(delta)
        per_label[label] = {
            "reference_rate": _safe_float(ref_rate),
            "current_rate": current_rate,
            "delta": delta,
            "drift_detected": bool(delta >= 0.05),
        }
    return {
        "target_drift_score": _safe_float(np.mean(deltas)) if deltas else 0.0,
        "label_stats": per_label,
    }


def compute_concept_proxy(
    current_metrics: dict[str, float],
    baseline_metrics: dict[str, float],
) -> dict[str, float | bool]:
    baseline_f1 = float(
        baseline_metrics.get("f1", current_metrics.get("f1", 0.0))
    )
    current_f1 = float(current_metrics.get("f1", 0.0))
    f1_drop = max(0.0, baseline_f1 - current_f1)

    baseline_cp_f1 = float(
        baseline_metrics.get("cp_f1", current_metrics.get("cp_f1", 0.0))
    )
    current_cp_f1 = float(current_metrics.get("cp_f1", 0.0))
    cp_f1_drop = max(0.0, baseline_cp_f1 - current_cp_f1)

    baseline_anomaly_rate = float(
        baseline_metrics.get(
            "anomaly_rate", current_metrics.get("anomaly_rate", 0.0)
        )
    )
    current_anomaly_rate = float(current_metrics.get("anomaly_rate", 0.0))
    anomaly_rate_shift = abs(baseline_anomaly_rate - current_anomaly_rate)

    score = _safe_float((f1_drop + cp_f1_drop + anomaly_rate_shift) / 3.0)
    return {
        "concept_drift_proxy_score": score,
        "f1_drop": _safe_float(f1_drop),
        "cp_f1_drop": _safe_float(cp_f1_drop),
        "anomaly_rate_shift": _safe_float(anomaly_rate_shift),
        "drift_detected": bool(
            score >= 0.07 or f1_drop >= 0.1 or cp_f1_drop >= 0.1
        ),
    }
