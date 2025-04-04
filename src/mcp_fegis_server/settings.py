"""
Settings module for Fegis.

Provides Pydantic settings classes for configuration of:
1. Qdrant vector database connection
2. Schema configuration file location
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class QdrantSettings(BaseSettings):
    """
    Qdrant vector database connection settings.

    These settings are loaded from environment variables:
    - QDRANT_URL: URL of the Qdrant server
    - QDRANT_GRPC_PORT: gRPC port for the Qdrant server
    - QDRANT_API_KEY: Optional API key for authentication
    - COLLECTION_NAME: Name of the collection to use
    - FAST_EMBED_MODEL: Name of the embedding model to use
    """
    qdrant_url: str = Field(
        validation_alias="QDRANT_URL",
    )
    grpc_port: int = Field(
        default=6334,
        validation_alias="QDRANT_GRPC_PORT",
        description="gRPC port for the Qdrant server (typically 6334)"
    )
    prefer_grpc: bool = Field(
        default=True,
        validation_alias="QDRANT_PREFER_GRPC",
        description="Whether to prefer gRPC over HTTP when possible"
    )
    qdrant_api_key: Optional[str] = Field(
        default=None,
        validation_alias="QDRANT_API_KEY",
        description="API key for Qdrant Cloud or authentication-enabled instances"
    )
    collection_name: str = Field(
        validation_alias="COLLECTION_NAME",
        description="Name of the Qdrant collection to store memories"
    )
    fast_embed_model: str = Field(
        validation_alias="FAST_EMBED_MODEL",
        description="Name of the embedding model to use (e.g., nomic-ai/nomic-embed-text-v1.5)"
    )


class ConfigSettings(BaseSettings):
    """
    Schema configuration settings.

    These settings are loaded from environment variables:
    - CONFIG_PATH: Path to the YAML configuration file
    """
    config_path: str = Field(
        default="config.yaml",
        validation_alias="CONFIG_PATH",
        description="Path to the YAML file containing the structured schema definition"
    )
