"""Configuration management with environment variable support and type safety.

This module provides the FegisConfig dataclass for managing server configuration
loaded from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

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
    search_tool_schema: SearchToolSchema | None = None

    def __post_init__(self):
        """Load the search tool schema from the JSON file after initialization."""
        import json
        from pathlib import Path
        schema_path = Path(__file__).parent / "search_tool_schema.json"
        try:
            with open(schema_path, encoding="utf-8") as f:
                self.search_tool_schema = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to load search tool schema: {e}") from e

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
