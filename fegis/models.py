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
    """Memory record with structured payload and search metadata."""

    title: str
    content: str = ""  # Document content from Qdrant
    context: str = ""
    tool: str

    session_id: str
    sequence_order: int
    memory_id: str
    timestamp: datetime
    preceding_memory_id: str | None = None

    parameters: dict[str, Any] = Field(default_factory=dict)
    frames: dict[str, Any] = Field(default_factory=dict)

    meta: MemoryMeta

    id: str | None = None  # Qdrant point ID (same as memory_id)
    score: float | None = None  # Search relevance score

    model_config = ConfigDict(from_attributes=True)
