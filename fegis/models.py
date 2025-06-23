# fegis/models.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryMeta(BaseModel):
    """Meta fields for system-level metadata."""

    agent_id: str
    schema_version: str
    fegis_version: str
    archetype_title: str
    archetype_version: str | float | None = None


class Memory(BaseModel):
    """A strongly-typed representation matching PAYLOAD_DESIGN.md structure."""

    # HUMAN-FIRST: What we care about seeing
    title: str
    content: str = ""  # Document content from Qdrant
    context: str = ""
    tool: str

    # RELATIONSHIP: How this connects to other memories
    session_id: str
    sequence_order: int
    memory_id: str
    timestamp: datetime
    preceding_memory_id: str | None = None

    # EXECUTION: The detailed work product
    parameters: dict[str, Any] = Field(default_factory=dict)
    frames: dict[str, Any] = Field(default_factory=dict)

    # META: System-level metadata for filtering and identification
    meta: MemoryMeta

    # SEARCH-ADDED: Fields added during search retrieval (not stored in payload)
    id: str | None = None  # Qdrant point ID (typically same as memory_id)
    score: float | None = None  # Search relevance score

    model_config = ConfigDict(from_attributes=True)
