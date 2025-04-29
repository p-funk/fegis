"""
QdrantConnector module for FEGIS.
Handles connection to Qdrant and sets up collections and indexes.
"""
from __future__ import annotations

import asyncio
import sys

from qdrant_client import AsyncQdrantClient

from .archetype_compiler import ArchetypeDefinition
from .constants import TOOL_NAME, USE_TITLE, TIMESTAMP, INDEX_TYPE_MAP
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
    """
    Wraps an AsyncQdrantClient and guarantees that the collection plus all
    payload indexes exist before the server starts accepting requests.
    """

    def __init__(self, cfg: QdrantSettings, schema: ArchetypeDefinition) -> None:
        self.col = cfg.collection_name
        self.schema = schema
        self.use_auto_id = cfg.use_auto_id

        print(f"Initializing QdrantConnector for collection: {self.col}", file=sys.stderr)

        # Use singleton client
        self.client = QdrantClientSingleton.get_instance(cfg)

        # Base payload index map for core metadata fields
        self._indexes: dict[str, str] = {
            TOOL_NAME: "keyword",
            USE_TITLE: "keyword",
            TIMESTAMP: "keyword",
        }

        # Dynamically build payload index map using updated ArchetypeDefinition API
        for mode_name in self.schema.tools():
            mode_model = self.schema.tool(mode_name)

            # Index facet fields
            for facet_field_name in (mode_model.processes or {}).keys():
                self._indexes[f"processes.{facet_field_name}"] = "keyword"

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
                            {"field_name": field, "field_schema": INDEX_TYPE_MAP[field_type]}
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
                            field_schema=INDEX_TYPE_MAP[field_type],
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
