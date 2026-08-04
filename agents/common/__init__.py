"""Shared helpers for ELT-Bench agent runners."""

from .warehouse import (
    DESTINATIONS,
    DestinationSpec,
    adapt_prompt,
    destination_choices,
    get_destination,
    prepare_destination,
    resolve_benchmark_path,
    resolve_inputs_path,
)

__all__ = [
    "DESTINATIONS",
    "DestinationSpec",
    "adapt_prompt",
    "destination_choices",
    "get_destination",
    "prepare_destination",
    "resolve_benchmark_path",
    "resolve_inputs_path",
]
