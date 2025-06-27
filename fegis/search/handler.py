"""The main handler for the search system that uses the Strategy pattern."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from .strategies import (
    BasicSearchStrategy,
    ByIdSearchStrategy,
    FilteredSearchStrategy,
    SearchStrategy,
)

if TYPE_CHECKING:
    from fegis.storage import QdrantStorage

__all__ = ["SearchHandler"]


class SearchHandler:
    """Dispatch search requests to the proper strategy and return memory dictionaries."""

    def __init__(self, storage: QdrantStorage) -> None:
        self._strategies: dict[str, SearchStrategy] = {
            "basic": BasicSearchStrategy(storage),
            "filtered": FilteredSearchStrategy(storage),
            "by_memory_id": ByIdSearchStrategy(storage),
        }

    async def search(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Executes a search and returns a list of memory dictionaries."""
        # Validate query for search types that require it
        search_type = params["search_type"]
        query = params["query"]

        if search_type in ["basic", "by_memory_id"] and (not query or not query.strip()):
            raise ValueError("Query cannot be empty for semantic and by_memory_id searches")

        strategy = self._strategies.get(search_type)
        if not strategy:
            raise ValueError(f"Unknown search type: {search_type}")

        logger.info(f"Dispatching to {search_type} strategy.")
        scored_points = await strategy.search(params)

        # Apply score threshold filtering (post-filtering due to hybrid RRF overwriting scores)
        score_threshold = params["score_threshold"]

        memories = []
        for point in scored_points:
            memory_dict = self._to_memory_dict(point)
            if memory_dict is not None and memory_dict["score"] >= score_threshold:
                memories.append(memory_dict)

        logger.info(
            f"Filtered {len(memories)} results above score threshold {score_threshold}"
        )
        return memories

    def _to_memory_dict(self, point: Any) -> dict[str, Any] | None:
        """Convert various Qdrant response objects to memory dictionaries."""
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

        return {"id": point.id, "score": score, "content": content, **payload}
