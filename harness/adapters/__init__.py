"""Project adapters for harness integration across evaluation modalities."""

from __future__ import annotations

from ..catalyst.notebook_validation import NotebookHttpClient
from ..validate.client import (
    ChartSearchAiClient,
    MedAgentHubClient,
    OpenAICompatibleClient,
)
from ..wahs.evaluator import WahsHubClient

TARGET_ADAPTERS: dict[str, type] = {
    "chartsearchai": ChartSearchAiClient,
    "med-agent-hub": MedAgentHubClient,
    "openai-compatible": OpenAICompatibleClient,
    "catalyst": NotebookHttpClient,
    "wahs": WahsHubClient,
}

__all__ = [
    "ChartSearchAiClient",
    "MedAgentHubClient",
    "OpenAICompatibleClient",
    "NotebookHttpClient",
    "WahsHubClient",
    "TARGET_ADAPTERS",
]
