"""Fegis MCP Server - Transform YAML archetypes into production MCP tools.

Fegis is an MCP server that converts structured prompt configurations (YAML archetypes)
into validated MCP tools with semantic memory. It provides:

- Dynamic tool generation from YAML archetype configurations
- Semantic memory storage with hybrid vector search via Qdrant
- Strategy-based search with configurable result views
- Production-ready MCP protocol compliance with JSON Schema validation

Key Components:
    FegisConfig: Configuration management with environment variables
    QdrantStorage: Vector database integration with hybrid search
    SearchHandler: Strategy-based search system

Example:
    >>> from fegis.config import FegisConfig
    >>> config = FegisConfig.from_env()

Architecture:
    YAML Archetype → fastjsonschema → MCP Tools → Memory Storage → Strategy-Based Search

"""

from __future__ import annotations

from .config import FegisConfig
from .storage import QdrantStorage
from .search import SearchHandler

__version__ = "2.0.0"
__all__ = [
    "FegisConfig",
    "QdrantStorage", 
    "SearchHandler",
]
