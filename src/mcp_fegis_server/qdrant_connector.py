from __future__ import annotations

import asyncio

from qdrant_client import AsyncQdrantClient

from .constants import MODE_FIELD, TITLE_FIELD
from .settings import QdrantSettings


class QdrantConnector:

    def __init__(self, cfg: QdrantSettings) -> None:
        self.col = cfg.collection_name

        self.client = AsyncQdrantClient(
            url=cfg.qdrant_url,
            api_key=cfg.qdrant_api_key,
            timeout=20,
        )
        self.client.set_model(cfg.fast_embed_model)

        # Only two payload indexes
        self._indexes: dict[str, str] = {
            MODE_FIELD: "keyword",
            TITLE_FIELD: "text",
        }

        self._ready = False

    async def ensure_ready(self) -> None:
        if self._ready:
            return

        # create collection if needed
        if not await self.client.collection_exists(self.col):
            await self.client.create_collection(
                collection_name=self.col,
                vectors_config=self.client.get_fastembed_vector_params(),
            )

        # make sure mode + title indexes exist
        await self._ensure_indexes()
        self._ready = True

    async def _ensure_indexes(self) -> None:
        info = await self.client.get_collection(self.col)
        existing = set((info.payload_schema or {}).keys())

        tasks = [
            self.client.create_payload_index(
                collection_name=self.col,
                field_name=field,
                field_schema=schema,
                wait=True,
            )
            for field, schema in self._indexes.items()
            if field not in existing
        ]

        if tasks:
            await asyncio.gather(*tasks)
