type JsonObject = Record<string, unknown>;

const DEFAULT_API_BASE_URL = "http://localhost:8000";

function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL;

  if (typeof window === "undefined") {
    return configured;
  }

  try {
    const url = new URL(configured);
    if (url.hostname === "api") {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
    if (url.hostname === "pardon-api") {
      return window.location.origin;
    }
  } catch {
    // Fall back to the configured value below when it is not an absolute URL.
  }

  return configured;
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>) {
  const url = new URL(path, getApiBaseUrl());
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let message = `API request failed with ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (payload.detail) {
        message =
          typeof payload.detail === "string"
            ? payload.detail
            : JSON.stringify(payload.detail);
      }
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

async function get<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> {
  return request<T>(buildUrl(path, params).toString());
}

async function post<T>(path: string, body: unknown, headers?: HeadersInit): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers,
  });
}

export type PredictRecord = {
  source_id: string | null;
  features: Record<string, number>;
};

export type PredictRequest = {
  model_name: string;
  records: PredictRecord[];
  request_id?: string;
};

export type PredictResponse = {
  request_id: string;
  model_name: string;
  predictions: {
    source_id: string | null;
    score: number;
    threshold: number;
    anomaly_flag: number;
  }[];
  drift: JsonObject;
};

export type RecentPrediction = {
  id: number;
  created_at: string;
  request_id: string;
  source_id: string | null;
  model_name: string;
  score: number;
  threshold: number;
  anomaly_flag: number;
};

export type AvailableModel = {
  model_name: string;
};

export type DatasetSource = {
  split: string;
  source_id: string;
  rows_count: number;
};

export type PredictionRunSummary = {
  request_id: string;
  model_name: string;
  created_at: string;
  records_count: number;
  anomalies_count: number;
  anomaly_rate: number;
  avg_score: number;
  max_score: number;
};

export type PredictionRunDetail = PredictionRunSummary & {
  rows: RecentPrediction[];
};

export type RetrainRequest = {
  model_name: string;
  dataset_scenario: string;
  register_model?: boolean;
};

export type RetrainJobResponse = {
  job_id: string;
  status: string;
  model_name: string;
  dataset_scenario: string;
  details: JsonObject;
};

export type DriftNotification = {
  id: number;
  created_at: string;
  severity: string;
  title: string;
  message: string;
  read: boolean;
};

export type Experiment = {
  run_id: string;
  experiment: string;
  model_name: string;
  status: string;
  started_at: string | null;
  metrics: Record<string, number>;
  params: Record<string, string>;
};

export type ExperimentDetail = Experiment & {
  tags: Record<string, string>;
};

export function runPredict(payload: PredictRequest): Promise<PredictResponse> {
  return post<PredictResponse>("/api/v1/predict", payload);
}

export function getAvailableModels(): Promise<AvailableModel[]> {
  return get<AvailableModel[]>("/api/v1/models/available");
}

export function getDatasetSources(split = "val", q?: string): Promise<DatasetSource[]> {
  return get<DatasetSource[]>("/api/v1/datasets/sources", { split, q });
}

export function getDatasetRecords(
  split: string,
  sourceId: string,
  limit = 50,
  offset = 0
): Promise<PredictRecord[]> {
  return get<PredictRecord[]>("/api/v1/datasets/records", {
    split,
    source_id: sourceId,
    limit,
    offset,
  });
}

export function getPredictionRuns(
  limit = 50,
  modelName?: string,
  offset = 0
): Promise<PredictionRunSummary[]> {
  return get<PredictionRunSummary[]>("/api/v1/predictions/runs", {
    limit,
    offset,
    model_name: modelName,
  });
}

export function getPredictionRunDetail(requestId: string): Promise<PredictionRunDetail> {
  return get<PredictionRunDetail>(`/api/v1/predictions/runs/${requestId}`);
}

export function getRecentPredictions(
  limit = 50,
  offset = 0,
  modelName?: string
): Promise<RecentPrediction[]> {
  return get<RecentPrediction[]>("/api/v1/predictions/recent", {
    limit,
    offset,
    model_name: modelName,
  });
}

export function getExperiments(
  limit = 30,
  modelName?: string,
  offset = 0
): Promise<Experiment[]> {
  return get<Experiment[]>("/api/v1/experiments", {
    limit,
    offset,
    model_name: modelName,
  });
}

export function getExperimentByRunId(runId: string): Promise<ExperimentDetail> {
  return get<ExperimentDetail>(`/api/v1/experiments/${runId}`);
}

export function getNotifications(
  limit = 50,
  offset = 0,
  onlyUnread = false
): Promise<DriftNotification[]> {
  return get<DriftNotification[]>("/api/v1/notifications/drift", {
    limit,
    offset,
    only_unread: onlyUnread,
  });
}

export function getActiveRetrain(): Promise<RetrainJobResponse | null> {
  return get<RetrainJobResponse | null>("/api/v1/retrain/active");
}

export function getRetrainStatus(jobId: string): Promise<RetrainJobResponse> {
  return get<RetrainJobResponse>(`/api/v1/retrain/${jobId}`);
}

export function startRetrain(
  modelName: string,
  datasetScenario: string
): Promise<RetrainJobResponse> {
  const token = process.env.NEXT_PUBLIC_RETRAIN_API_TOKEN;
  return post<RetrainJobResponse>(
    "/api/v1/retrain",
    {
      model_name: modelName,
      dataset_scenario: datasetScenario,
      register_model: true,
    } satisfies RetrainRequest,
    token ? { Authorization: `Bearer ${token}` } : undefined
  );
}
