from __future__ import annotations

from dataclasses import dataclass, field
import time

from loguru import logger

try:
    from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
except ModuleNotFoundError:  # pragma: no cover
    CollectorRegistry = None
    Gauge = None
    push_to_gateway = None


@dataclass
class MonitoringEmitter:
    job_name: str
    enabled: bool
    pushgateway_url: str = ""
    grouping_key: dict[str, str] = field(default_factory=dict)
    _registry: CollectorRegistry | None = None
    _gauges: dict[str, Gauge] = field(default_factory=dict)
    _start_time: float = field(default_factory=time.perf_counter)

    def __post_init__(self) -> None:
        self.enabled = bool(
            self.enabled and CollectorRegistry is not None and Gauge is not None
        )
        if self.enabled:
            self._registry = CollectorRegistry()

    def gauge(self, name: str, description: str, value: float) -> None:
        if not self.enabled or self._registry is None:
            return
        gauge = self._gauges.get(name)
        if gauge is None:
            gauge = Gauge(name, description, registry=self._registry)
            self._gauges[name] = gauge
        gauge.set(float(value))

    def observe_runtime(self) -> None:
        elapsed = time.perf_counter() - self._start_time
        self.gauge(
            "anomaly_pipeline_job_duration_seconds",
            "Runtime of the finished train/predict job in seconds.",
            elapsed,
        )

    def flush(self) -> None:
        if (
            not self.enabled
            or not self.pushgateway_url
            or self._registry is None
        ):
            return
        if push_to_gateway is None:  # pragma: no cover
            return
        try:
            push_to_gateway(
                gateway=self.pushgateway_url,
                job=self.job_name,
                registry=self._registry,
                grouping_key=self.grouping_key,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not push metrics to Pushgateway: {}", exc)
