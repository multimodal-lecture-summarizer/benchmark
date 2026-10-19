"""Actual environment observation and bounded scorer-only resource sampling."""
import importlib.metadata
import platform
import threading
import time
import math
import os
import re


def effective_package_versions():
    """Resolve effective sys.path precedence, including inherited venv packages.

    distributions() can enumerate a venv distribution followed by its shadowed
    system copy. Metadata.version uses normal first-match resolution instead.
    """
    names = {re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower()
             for distribution in importlib.metadata.distributions()
             if distribution.metadata.get("Name")}
    return {name: importlib.metadata.version(name) for name in sorted(names)}


def observe_runtime():
    import torch
    try:
        import google.colab
        colab, colab_module = True, getattr(google.colab, "__file__", None)
    except ImportError:
        colab, colab_module = False, None
    cuda = bool(torch.cuda.is_available())
    device = torch.cuda.get_device_name(0) if cuda else None
    versions = effective_package_versions()
    return {"google_colab_imported": colab, "google_colab_module": colab_module,
            "cuda_available": cuda, "device_name": device,
            "T4_device_observed": device in ("Tesla T4", "NVIDIA T4", "NVIDIA Tesla T4"),
            "device_memory_bytes": torch.cuda.get_device_properties(0).total_memory if cuda else None,
            "cuda_runtime": torch.version.cuda, "python": platform.python_version(),
            "platform": platform.platform(), "packages": versions,
            "logical_cpu_count": os.cpu_count(), "torch_cpu_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads()}


class ResourceSampler:
    def __init__(self):
        import psutil
        self.process = psutil.Process()
        self.psutil = psutil
        self.peak = self.process.memory_info().rss
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.started, self.cpu_started = time.perf_counter(), time.process_time()
        self.cuda = False

    def _sample(self):
        while not self.stop.wait(0.1):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def start(self):
        import torch
        self.cuda = bool(torch.cuda.is_available())
        if self.cuda:
            torch.cuda.reset_peak_memory_stats()
        self.thread.start()
        return self

    def finish(self):
        import torch
        self.stop.set()
        self.thread.join()
        self.peak = max(self.peak, self.process.memory_info().rss)
        return {"wall_seconds": time.perf_counter() - self.started,
                "cpu_seconds": time.process_time() - self.cpu_started,
                "sampled_peak_process_rss_bytes": self.peak,
                "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if self.cuda else None,
                "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved() if self.cuda else None,
                "host_memory_total_bytes": self.psutil.virtual_memory().total,
                "host_memory_available_bytes": self.psutil.virtual_memory().available,
                "measurement_note": "sampled process RSS; CUDA peaks include init/fixtures/scoring, not GPU generation"}


def synchronize():
    import torch
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def resource_errors(resources):
    positive = ("wall_seconds", "cpu_seconds", "sampled_peak_process_rss_bytes",
                "cuda_peak_allocated_bytes", "cuda_peak_reserved_bytes", "host_memory_total_bytes")
    return ["missing_or_invalid_resource_" + key for key in positive
            if not isinstance(resources.get(key), (int, float))
            or isinstance(resources.get(key), bool)
            or not math.isfinite(resources[key]) or resources[key] <= 0]


def input_profile(row, scorer):
    """Describe actual token routing without changing text or metric policy."""
    from .rq2_tib_benchmark_metrics import sentences
    result = {key + "_whitespace_words": len(row[key].split())
              for key in ("source", "reference", "delivered_summary")}
    parts = sentences(row["source"])
    result["source_sentence_count"] = len(parts)
    bert = getattr(getattr(scorer, "_bert", None), "_tokenizer", None)
    if bert is not None:
        counts = {key: len(bert.encode(row[key], add_special_tokens=False, truncation=False))
                  for key in ("reference", "delivered_summary")}
        result["bertscore_content_tokens"] = counts
        result["bertscore_route"] = "native" if max(counts.values()) <= 510 else "window_extension"
        result["bertscore_content_windows"] = {key: max(1, math.ceil(value / 510)) for key, value in counts.items()}
    return result


def latency_description(values):
    values = sorted(values)
    if not values:
        return {"record_count": 0, "p50_seconds": None, "p95_seconds": None, "max_seconds": None}
    def percentile(fraction):
        position = (len(values) - 1) * fraction
        lower, upper = math.floor(position), math.ceil(position)
        return values[lower] + (values[upper] - values[lower]) * (position - lower)
    return {"record_count": len(values), "p50_seconds": percentile(0.5),
            "p95_seconds": percentile(0.95), "max_seconds": values[-1],
            "method": "linear_interpolation_on_observed_records",
            "claim_limit": "descriptive three-source development timing; not future budget or population tail estimate"}
