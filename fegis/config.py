"""Configuration management with environment variable support and type safety.

This module provides the FegisConfig dataclass for managing server configuration
loaded from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from typing_extensions import TypedDict

__all__ = [
    "FegisConfig",
    "TransportType",
    "SearchToolSchema",
]


class TransportType(str, Enum):
    """Supported MCP transport types."""

    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


class SearchToolSchema(TypedDict):
    """Type definition for the SearchMemory tool schema."""

    name: str
    description: str
    inputSchema: dict[str, Any]


@dataclass
class FegisConfig:
    """Configuration for Fegis server loaded from environment variables."""

    # Required configuration
    archetype_path: str

    # Optional configuration with defaults
    qdrant_url: str = "http://localhost:6333"
    collection_name: str = "fegis_memory"
    embedding_model: str = "BAAI/bge-small-en"
    agent_id: str = "default-agent"
    qdrant_api_key: str | None = None
    prefer_grpc: bool = True
    grpc_port: int = 6334
    transport: str = TransportType.STDIO.value
    server_name: str = "fegis"
    schema_version: str = "1.0"
    fegis_version: str = "2.0.0"
    debug: bool = False

    # Built-in search tool schema, as defined in the documentation
    SEARCH_TOOL: ClassVar[SearchToolSchema] = {
        "name": "SearchMemory",
        "description": "Search your stored memories using semantic search.\n\nThree search types available: basic (semantic), filtered (by criteria), by_memory_id (specific memory UUID).\n\nFour result views: compact (essential fields), summary (browseable preview), graph (relational metadata network), full (complete memory with metadata).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query or a memory UUID.",
                    "maxLength": 1000,
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of memories to show",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 100,
                },
                "search_type": {
                    "type": "string",
                    "enum": ["basic", "filtered", "by_memory_id"],
                    "description": "Recall strategy.",
                    "default": "basic",
                },
                "filters": {
                    "type": "array",
                    "description": "One or more query filters.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "string",
                                "enum": [
                                    "session_id",
                                    "tool",
                                    "agent_id",
                                    "title",
                                    "context",
                                    "sequence_order",
                                    "memory_id",
                                    "timestamp",
                                    "preceding_memory_id",
                                    "archetype_title",
                                    "archetype_version",
                                    "schema_version",
                                ],
                                "description": "Which field to filter on.",
                            },
                            "operator": {
                                "type": "string",
                                "enum": [
                                    "is",
                                    "is_not",
                                    "before",
                                    "after",
                                    "between",
                                    "contains",
                                    "any_of",
                                ],
                                "description": "How to match the field: 'is' for exact match, 'is_not' to exclude, 'before/after' for time/order, 'between' for ranges, 'contains' for text search, 'any_of' for multiple options.",
                            },
                            "value": {
                                "description": "Value to match against. Use array [min,max] for 'between', array [item1,item2] for 'any_of', single value for others.",
                                "oneOf": [
                                    {"type": "string"},
                                    {"type": "number"},
                                    {"type": "array"},
                                    {
                                        "type": "object",
                                        "properties": {"from": {}, "to": {}},
                                        "required": ["from", "to"],
                                        "additionalProperties": False,
                                    },
                                ],
                            },
                        },
                        "required": ["field", "operator", "value"],
                        "additionalProperties": False,
                    },
                },
                "detail": {
                    "type": "string",
                    "enum": ["compact", "summary", "graph", "full"],
                    "description": "How much context you want to see: compact (essentials), summary (overview), graph (relational metadata network), full (complete with procedural and episodic memory).",
                    "default": "summary",
                },
                "score_threshold": {
                    "type": "number",
                    "description": "Minimum relevance score (0.0-1.0). Higher values return only more relevant results. Use 0.0 for broad exploration, 0.4+ for precise matches.",
                    "default": 0.4,
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    }

    @classmethod
    def from_env(cls) -> FegisConfig:
        """Load configuration from environment variables."""
        archetype_path = os.getenv("ARCHETYPE_PATH")
        if not archetype_path:
            raise ValueError("ARCHETYPE_PATH environment variable is required")

        return cls(
            archetype_path=archetype_path,
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            collection_name=os.getenv("COLLECTION_NAME", "fegis_memory"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en"),
            agent_id=os.getenv("AGENT_ID", "default-agent"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            prefer_grpc=os.getenv("PREFER_GRPC", "true").lower() == "true",
            grpc_port=int(os.getenv("GRPC_PORT", "6334")),
            transport=os.getenv("TRANSPORT", "stdio"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )
