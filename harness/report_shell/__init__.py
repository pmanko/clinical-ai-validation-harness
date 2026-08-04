"""Shared HTML report shell used by multiple validation report families."""

from harness.report_shell.document import render_document
from harness.report_shell.stats import avg, box_stats, ordered_unique, percentile, robust_axis_max

__all__ = [
    "avg",
    "box_stats",
    "ordered_unique",
    "percentile",
    "render_document",
    "robust_axis_max",
]
