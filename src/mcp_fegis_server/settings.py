"""
Settings module for FEGIS.

Provides Pydantic settings classes for configuration of:
1. Qdrant vector database connection
2. Archetype configuration file location
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class QdrantSettings(BaseSettings):
    """
    Qdrant vector database connection settings.

    These settings are loaded from environment variables:
    - QDRANT_URL: URL of the Qdrant server
    - QDRANT_API_KEY: Optional API key for authentication
    - COLLECTION_NAME: Name of the collection to use
    - FAST_EMBED_MODEL: Name of the embedding model to use
    """
    qdrant_url: str = Field(
        validation_alias="QDRANT_URL",
    )
    qdrant_api_key: Optional[str] = Field(
        default=None,
        validation_alias="QDRANT_API_KEY",
    )
    collection_name: str = Field(
        validation_alias="COLLECTION_NAME",
    )
    fast_embed_model: str = Field(
        validation_alias="FAST_EMBED_MODEL",
    )


class ConfigSettings(BaseSettings):
    """
    Archetype configuration settings.

    These settings are loaded from environment variables:
    - CONFIG_PATH: Path to the YAML archetype definition file
    """
    config_path: str = Field(
        default=".archetypes/example.yaml",
        validation_alias="CONFIG_PATH",
        description="Path to the YAML file containing the archetype definition"
    )
