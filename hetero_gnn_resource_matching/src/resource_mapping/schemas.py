"""Typed schemas used by the prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ResourceNode:
    """A single typed resource node."""

    id: str
    type: str
    node_id: str | None = None
    rack_id: str | None = None
    switch_id: str | None = None
    features: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResourceEdge:
    """A typed edge between resource nodes."""

    source: str
    target: str
    relation: str
    source_type: str
    target_type: str
    features: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Task:
    """Task requirements consumed by the matcher."""

    task_id: str
    task_type: str
    dominant_mode: str
    requirements: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CandidateSubnet:
    """A candidate resource subnet for one task."""

    candidate_id: str
    task_id: str
    nodes: dict[str, list[str]]
