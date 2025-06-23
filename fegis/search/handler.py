"""The main handler for the search system that uses the Strategy pattern."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from ..models import Memory  # <-- Import the new model
from .strategies import (
    ByIdSearchStrategy,
    DefaultSearchStrategy,
    FilteredSearchStrategy,
    SearchStrategy,
)

if TYPE_CHECKING:
    from fegis.storage import QdrantStorage


class SearchHandler:
    """Dispatch search requests to the proper strategy and return ``Memory`` objects."""

    def __init__(self, storage: QdrantStorage):
        self._strategies: dict[str, SearchStrategy] = {
            "default": DefaultSearchStrategy(storage),
            "filtered": FilteredSearchStrategy(storage),
            "by_id": ByIdSearchStrategy(storage),
        }

    async def search(
        self, params: dict[str, Any]
    ) -> list[Memory]:  # <-- Updated return type
        """Executes a search and returns a list of memory objects."""
        # Validate query for search types that require it
        search_type = params["search_type"]
        query = params["query"]

        if search_type in ["default", "by_id"] and (not query or not query.strip()):
            raise ValueError("Query cannot be empty for semantic and by-id searches")

        strategy = self._strategies.get(search_type)
        if not strategy:
            raise ValueError(f"Unknown search type: {search_type}")

        logger.info(f"Dispatching to {search_type} strategy.")
        scored_points = await strategy.search(params)

        # Apply score threshold filtering (post-filtering due to RRF overwriting scores)
        score_threshold = params["score_threshold"]

        memories = []
        for point in scored_points:
            memory = self._to_memory(point)
            if memory is not None and memory.score >= score_threshold:
                memories.append(memory)

        logger.info(
            f"Filtered {len(memories)} results above score threshold {score_threshold}"
        )
        return memories

    def _to_memory(self, point: Any) -> Memory | None:
        """Convert various Qdrant response objects to ``Memory`` instances."""
        if hasattr(point, "metadata"):
            payload = point.metadata
            content = point.document or ""
            score = getattr(point, "score", 0.0)
        elif hasattr(point, "payload"):
            payload = point.payload
            content = payload.get("document", payload.get("content", ""))
            score = getattr(point, "score", 0.0)
        else:
            logger.warning(f"Unknown response object type: {type(point)}")
            return None

        if not payload:
            return None

        data = {"id": point.id, "score": score, "content": content, **payload}

        try:
            return Memory.model_validate(data)
        except Exception as e:  # pragma: no cover - validation edge cases
            logger.error(f"Failed to validate memory object with id {point.id}: {e}")
            return None
