"""Fegis MCP Server - Transform YAML archetypes into production MCP tools.

Fegis is an MCP server that converts structured prompt configurations (YAML archetypes)
into validated MCP tools with semantic memory. It provides:

- Dynamic tool generation from YAML archetype configurations
- Semantic memory storage with hybrid vector search via Qdrant
- Strategy-based search with configurable result views
- Production-ready MCP protocol compliance with JSON Schema validation

Key Components:
    FegisConfig: Configuration management with environment variables
    Memory: Pydantic models for type-safe memory objects
    MemoryMeta: Metadata structure for memory attribution
    QdrantStorage: Vector database integration with hybrid search
    SearchHandler: Strategy-based search system

Example:
    >>> from fegis.config import FegisConfig
    >>> config = FegisConfig.from_env()
    >>> # Start MCP server: uv run fegis --transport stdio --archetype-path archetypes/default.yaml

Architecture:
    YAML Archetype → Pydantic Schema → MCP Tools → Memory Storage → Strategy-Based Search

For more information, see the CLAUDE.md file in the repository root.
"""

from __future__ import annotations

from .config import FegisConfig
from .models import Memory, MemoryMeta

__version__ = "2.0.0"
__all__ = [
    "FegisConfig",
    "Memory",
    "MemoryMeta",
]
