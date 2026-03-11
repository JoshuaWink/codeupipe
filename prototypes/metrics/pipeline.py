"""
Metrics pipeline builder — composes the metric filters into a Pipeline.

Usage:
    from prototypes.metrics.pipeline import build_metrics_pipeline
    pipeline = build_metrics_pipeline()
    result = await pipeline.run(payload)
"""

import sys
from pathlib import Path

_proto_dir = Path(__file__).parent
_repo_root = _proto_dir.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from codeupipe import Pipeline

from .latency_probe import LatencyProbe
from .bundle_size_check import BundleSizeCheck
from .health_poller import HealthPoller
from .assemble_metrics_report import AssembleMetricsReport

__all__ = ["build_metrics_pipeline"]


def build_metrics_pipeline(
    requests: int = 10,
    polls: int = 10,
    poll_interval: float = 1.0,
    warn_bytes: int = 5_000_000,
) -> Pipeline:
    """Build a metrics validation pipeline.

    Args:
        requests: Number of HTTP requests per endpoint for latency probing.
        polls: Number of health polls.
        poll_interval: Seconds between health polls.
        warn_bytes: Bundle size warning threshold in bytes.

    Returns:
        A wired Pipeline ready to run.
    """
    pipeline = Pipeline()
    pipeline.add_filter(LatencyProbe(requests=requests), name="latency_probe")
    pipeline.add_filter(BundleSizeCheck(warn_bytes=warn_bytes), name="bundle_size_check")
    pipeline.add_filter(HealthPoller(polls=polls, interval_s=poll_interval), name="health_poller")
    pipeline.add_filter(AssembleMetricsReport(), name="assemble_report")
    pipeline.observe(timing=True)
    return pipeline
