"""
Qdrant Vector Database Integration for Trace Archive

Manages trace storage and retrieval using Qdrant's vector database interface:

1. Connection Management: Singleton pattern for efficient resource usage
2. Collection Initialization: Dynamic creation of collections with proper schema
3. Index Management: Creating payload indexes for efficient filtering
4. Query Optimization: Supporting both vector similarity and metadata filtering

The connector automatically builds a schema based on the loaded archetype,
creating appropriate indexes for:
- Tool names (keyword exact match)
- Parameter values (keyword faceting)
- Frame field values (type-appropriate indexing)
- Timestamp values (for chronological navigation)

"""

from __future__ import annotations

import asyncio
import sys

from qdrant_client import AsyncQdrantClient

from .archetype_compiler import ArchetypeDefinition
from .constants import INDEX
from .settings import QdrantSettings


# Client singleton
class QdrantClientSingleton:
    _instance = None

    @classmethod
    def get_instance(cls, cfg: QdrantSettings):
        if cls._instance is None:
            print(f"Creating QdrantClient singleton", file=sys.stderr)
            cls._instance = AsyncQdrantClient(
                url=cfg.qdrant_url,
                api_key=cfg.qdrant_api_key,
                timeout=20,
            )
            cls._instance.set_model(cfg.fast_embed_model)
        return cls._instance

# Collection info cache
_collection_info_cache = {}


class QdrantConnector:
    """Vector database abstraction for the Trace Archive.

    Manages the lifecycle of Qdrant collections, handling:
    1. Connection pooling and resource management
    2. Dynamic schema generation from archetypes
    3. Index creation
    4. Runtime query execution

    The connector builds a comprehensive index map based on the archetype schema,
    ensuring that all searchable fields have appropriate indexes for performant
    filtering. It uses a combination of:
    - Vector similarity for semantic matching
    - Payload indexes for exact/faceted filtering

    Collection information is cached to avoid redundant API calls during normal
    operation, with connection pooling.
    """

    def __init__(self, cfg: QdrantSettings, schema: ArchetypeDefinition) -> None:
        self.col = cfg.collection_name
        self.schema = schema

        print(f"Initializing QdrantConnector for collection: {self.col}", file=sys.stderr)

        # Use singleton client
        self.client = QdrantClientSingleton.get_instance(cfg)

        # Base payload index map for core metadata fields
        self._indexes: dict[str, str] = {
            "tool": "keyword",
            "title": "keyword",
            "timestamp": "keyword",
        }

        # Dynamically build payload index map using updated ArchetypeDefinition API
        for mode_name in self.schema.tools():
            mode_model = self.schema.tool(mode_name)

            # Index facet fields
            for facet_field_name in (mode_model.parameters or {}).keys():
                self._indexes[f"parameters.{facet_field_name}"] = "keyword"

            # Index frames (List, bool, float) fields
            for frames_field_name in self.schema.frame_fields(mode_name):
                self._indexes[f"frames.{frames_field_name}"] = "keyword"

        print(f"Built index map with {len(self._indexes)} fields.  Updating collection index", file=sys.stderr)
        self._ready = False

    async def ensure_ready(self) -> None:
        if self._ready:
            return

        try:
            # Create collection if needed
            if not await self.client.collection_exists(self.col):
                print(f"Creating collection: {self.col}", file=sys.stderr)
                await self.client.create_collection(
                    collection_name=self.col,
                    vectors_config=self.client.get_fastembed_vector_params(),
                )
            elif self.col in _collection_info_cache:
                # Use cached collection info
                print(f"Using cached collection info for {self.col}", file=sys.stderr)
                self._ready = True
                return

            # Ensure all relevant indexes are created
            await self._ensure_indexes()
            self._ready = True
            print(f"Collection {self.col} is ready", file=sys.stderr)
        except Exception as e:
            print(f"Error during collection setup: {e}", file=sys.stderr)
            raise

    async def _ensure_indexes(self) -> None:
        try:
            info = await self.client.get_collection(self.col)
            # Cache collection info
            _collection_info_cache[self.col] = info

            existing = set((info.payload_schema or {}).keys())

            # Get missing indexes
            missing_indexes = [
                (field, field_type)
                for field, field_type in self._indexes.items()
                if field not in existing
            ]

            if missing_indexes:
                print(f"Creating {len(missing_indexes)} missing indexes", file=sys.stderr)

                # Check if batch index creation is available
                if hasattr(self.client, "create_payload_index_batch"):
                    # Use batch index creation
                    await self.client.create_payload_index_batch(
                        collection_name=self.col,
                        field_configs=[
                            {"field_name": field, "field_schema": INDEX[field_type]}
                            for field, field_type in missing_indexes
                        ],
                        wait=True,
                    )
                else:
                    # Fallback to individual index creation
                    tasks = [
                        self.client.create_payload_index(
                            collection_name=self.col,
                            field_name=field,
                            field_schema=INDEX[field_type],
                            wait=True,
                        )
                        for field, field_type in missing_indexes
                    ]
                    await asyncio.gather(*tasks)
            else:
                print("All indexes already exist", file=sys.stderr)

        except Exception as e:
            print(f"Error creating indexes: {e}", file=sys.stderr)
            raise