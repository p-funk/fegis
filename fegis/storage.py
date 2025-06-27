"""Handles interaction with the Qdrant vector database."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from loguru import logger
from qdrant_client import AsyncQdrantClient, models

if TYPE_CHECKING:
    from .config import FegisConfig

__all__ = ["QdrantStorage"]


class QdrantStorage:
    """Manages all communication with the Qdrant collection."""

    def __init__(self, config: FegisConfig) -> None:
        self.config = config
        self.collection_name = config.collection_name
        self.client = AsyncQdrantClient(
            url=config.qdrant_url,
            api_key=config.qdrant_api_key,
            prefer_grpc=config.prefer_grpc,
            grpc_port=config.grpc_port,
        )

    async def initialize(self) -> None:
        """Sets up embedding models and ensures the collection exists."""
        import sys

        print(
            "[INIT] Initializing Qdrant storage and embedding models...",
            file=sys.stderr,
        )

        print(
            f"[INIT] Setting dense embedding model: {self.config.embedding_model}",
            file=sys.stderr,
        )
        self.client.set_model(self.config.embedding_model)
        print("[OK] Dense model ready", file=sys.stderr)

        try:
            exists = await self.client.collection_exists(self.collection_name)
            if exists:
                logger.info(f"Collection '{self.collection_name}' already exists.")
            else:
                logger.info(f"Creating collection '{self.collection_name}'.")
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=self.client.get_fastembed_vector_params(),
                )
        except Exception as e:
            logger.error(f"Error checking/creating collection: {e}")
            raise
        await self.ensure_indexes()

    async def ensure_indexes(self) -> None:
        """Creates indexes for the semantic-first payload structure."""
        desired_indexes = {
            "title": models.PayloadSchemaType.TEXT,
            "context": models.PayloadSchemaType.TEXT,
            "tool": models.PayloadSchemaType.KEYWORD,
            "session_id": models.PayloadSchemaType.KEYWORD,
            "sequence_order": models.PayloadSchemaType.INTEGER,
            "memory_id": models.PayloadSchemaType.KEYWORD,
            "timestamp": models.PayloadSchemaType.DATETIME,
            "preceding_memory_id": models.PayloadSchemaType.KEYWORD,
            "meta.agent_id": models.PayloadSchemaType.KEYWORD,
            "meta.archetype_title": models.PayloadSchemaType.KEYWORD,
            "meta.archetype_version": models.PayloadSchemaType.KEYWORD,
            "meta.schema_version": models.PayloadSchemaType.KEYWORD,
        }
        try:
            collection_info = await self.client.get_collection(self.collection_name)
            existing_indexes = (
                set(collection_info.payload_schema.keys())
                if collection_info.payload_schema
                else set()
            )
            missing_indexes = {
                k: v for k, v in desired_indexes.items() if k not in existing_indexes
            }
            if not missing_indexes:
                logger.info("All required payload indexes are in place.")
                return

            logger.info(f"Creating missing indexes: {list(missing_indexes.keys())}")
            for field_name, schema_type in missing_indexes.items():
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                    wait=True,
                )
            logger.info("Successfully created payload indexes.")
        except Exception as e:
            logger.error(f"Failed to ensure indexes: {e}")

    async def get_last_memory_for_session(
        self, session_id: str
    ) -> tuple[str | None, int]:
        """Get the most recent memory ID and next sequence order for a given session."""
        try:
            # Query for memories in this session, get more records to find the max sequence
            session_memories, _ = await self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="session_id", match=models.MatchValue(value=session_id)
                        )
                    ]
                ),
                limit=50,  # Get more records to find max sequence
                with_payload=True,
                with_vectors=False,
            )

            if session_memories:
                # Find the memory with the highest sequence_order
                latest_memory = max(
                    session_memories, key=lambda x: x.payload.get("sequence_order", 0)
                )
                last_memory_id = latest_memory.payload.get("memory_id")
                last_sequence_number = latest_memory.payload.get("sequence_order", 0)
                next_sequence_number = last_sequence_number + 1
                return last_memory_id, next_sequence_number

            # No memories in this session yet
            return None, 1

        except Exception as e:
            logger.error(f"Failed to get last memory for session {session_id}: {e}")
            return None, 1

    async def store_invocation(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        frames: dict[str, Any],
        archetype: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        """Stores the result of a tool invocation and returns its new ID."""
        memory_title = parameters.get("Title", f"{tool_name} Invocation")
        memory_context = parameters.get("Context", "")
        memory_content = parameters.get("Content", "")

        document_text = (
            memory_content or f"Tool: {tool_name}\n{json.dumps(frames, indent=2)}"
        )

        filtered_parameters = {
            k: v
            for k, v in parameters.items()
            if k not in ["Title", "Content", "Context"]
        }
        filtered_frames = {
            k: v for k, v in frames.items() if k not in ["Title", "Content", "Context"]
        }

        memory_id = str(uuid.uuid4())

        memory_payload = {
            "title": memory_title,
            "context": memory_context,
            "tool": tool_name,
            "session_id": context.get("session_id"),
            "sequence_order": context.get("sequence_order", 0),
            "memory_id": memory_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "preceding_memory_id": context.get("preceding_memory_id"),
            "parameters": filtered_parameters,
            "frames": filtered_frames,
            "meta": {
                "agent_id": self.config.agent_id,
                "schema_version": self.config.schema_version,
                "fegis_version": self.config.fegis_version,
                "archetype_title": archetype.get("title", "unknown"),
                "archetype_version": archetype.get("version", "unknown"),
            },
        }

        logger.info(f"'{tool_name}' stored with memory_id '{memory_id}'")
        await self.client.add(
            collection_name=self.collection_name,
            documents=[document_text],
            metadata=[memory_payload],
            ids=[memory_id],
        )
        return memory_id

    async def close(self) -> None:
        """Closes the connection to Qdrant."""
        await self.client.close()
