"""
Implements the Strategy pattern for different search methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

from loguru import logger
from qdrant_client import models

if TYPE_CHECKING:
    from fegis.storage import QdrantStorage

__all__ = [
    "SearchType",
    "SearchStrategy",
    "BasicSearchStrategy",
    "FilteredSearchStrategy",
    "ByIdSearchStrategy",
]


class SearchType(str, Enum):
    """Available search strategies."""

    BASIC = "basic"
    FILTERED = "filtered"
    BY_MEMORY_ID = "by_memory_id"


class SearchStrategy(ABC):
    """Abstract base class for a search strategy."""

    def __init__(self, storage: QdrantStorage):
        self.storage = storage

    @abstractmethod
    async def search(self, params: dict[str, Any]) -> list[models.ScoredPoint]:
        """Executes a search query and returns a list of ScoredPoint objects."""
        pass

    def _build_structured_filter(self, params: dict[str, Any]) -> models.Filter | None:
        """Convert filter parameters into Qdrant filter conditions."""
        filters = params.get("filters", [])
        if not filters:
            return None

        # Validate filters before processing
        self._validate_filters(filters)

        must_conditions = []

        for filter_spec in filters:
            field = filter_spec["field"]
            operator = filter_spec["operator"]
            value = filter_spec["value"]

            # Map field names to Qdrant payload paths
            field_key = self._map_field_to_key(field)

            # Build condition based on operator
            condition = self._build_condition(field_key, operator, value)
            if condition:
                must_conditions.append(condition)

        return models.Filter(must=must_conditions) if must_conditions else None

    def _map_field_to_key(self, field: str) -> str:
        """Map schema field names to Qdrant payload keys."""
        field_mapping = {
            "agent_id": "meta.agent_id",
            "archetype_title": "meta.archetype_title",
            "archetype_version": "meta.archetype_version",
            "schema_version": "meta.schema_version",
        }
        return field_mapping.get(field, field)

    def _validate_filters(self, filters: list[dict[str, Any]]) -> None:
        """Check filter field names, operators, and required parameters."""
        valid_operators = [
            "is",
            "is_not",
            "contains",
            "after",
            "before",
            "between",
            "any_of",
        ]
        valid_fields = [
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
        ]

        for filter_spec in filters:
            # Check required fields
            if "field" not in filter_spec:
                raise ValueError("Filter missing required 'field' parameter")
            if "operator" not in filter_spec:
                raise ValueError("Filter missing required 'operator' parameter")
            if "value" not in filter_spec:
                raise ValueError("Filter missing required 'value' parameter")

            # Validate field name
            field = filter_spec["field"]
            if field not in valid_fields:
                raise ValueError(
                    f"Invalid field '{field}'. Valid fields: {valid_fields}"
                )

            # Validate operator
            operator = filter_spec["operator"]
            if operator not in valid_operators:
                raise ValueError(
                    f"Invalid operator '{operator}'. Valid operators: {valid_operators}"
                )

            # Validate date formats for timestamp fields
            field = filter_spec["field"]
            value = filter_spec["value"]
            if field == "timestamp" and operator in ["after", "before"]:
                if not isinstance(value, str):
                    raise ValueError(
                        "Timestamp filter values must be strings in ISO format"
                    )
                try:
                    from datetime import datetime

                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as e:
                    raise ValueError(
                        f"Invalid timestamp format '{value}'. Use ISO format (e.g., '2024-01-01T00:00:00Z')"
                    ) from e

    def _build_condition(
        self, field_key: str, operator: str, value
    ) -> models.Condition | None:
        """Build a Qdrant condition from instructional operator and value."""
        builders = {
            "is": lambda: models.FieldCondition(
                key=field_key, match=models.MatchValue(value=value)
            ),
            "is_not": lambda: models.FieldCondition(
                key=field_key, match=models.MatchExcept(**{"except": [value]})
            ),
            "before": lambda: models.FieldCondition(
                key=field_key, range=models.Range(lt=value)
            ),
            "after": lambda: models.FieldCondition(
                key=field_key, range=models.Range(gt=value)
            ),
            "between": lambda: self._build_range_condition(field_key, value),
            "contains": lambda: self._build_contains_condition(field_key, value),
            "any_of": lambda: self._build_array_condition(field_key, value),
        }

        if operator not in builders:
            logger.warning(f"Unknown operator: {operator}")
            return None

        try:
            return builders[operator]()
        except Exception as e:
            logger.error(f"Error building {operator} condition: {e}")
            return None

    def _build_range_condition(self, field_key: str, value) -> models.Condition:
        """Build range condition with validation."""
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("'between' operator requires array [min, max]")
        return models.FieldCondition(
            key=field_key, range=models.Range(gte=value[0], lte=value[1])
        )

    def _build_array_condition(self, field_key: str, value) -> models.Condition:
        """Build array condition with validation."""
        if not isinstance(value, list):
            raise ValueError("'any_of' operator requires array")
        return models.FieldCondition(key=field_key, match=models.MatchAny(any=value))

    def _build_contains_condition(self, field_key: str, value) -> models.Condition:
        """Build contains condition with case-insensitive and fuzzy matching."""
        if not isinstance(value, str):
            # For non-string values, use exact text matching
            return models.FieldCondition(
                key=field_key, match=models.MatchText(text=str(value))
            )

        # Create multiple conditions for flexible matching
        search_value = value.lower()
        conditions = []

        # Exact match (case-insensitive)
        conditions.append(
            models.FieldCondition(
                key=field_key, match=models.MatchText(text=search_value)
            )
        )

        # Original case match
        if value != search_value:
            conditions.append(
                models.FieldCondition(key=field_key, match=models.MatchText(text=value))
            )

        # Capitalize first letter
        capitalized = value.capitalize()
        if capitalized not in [value, search_value]:
            conditions.append(
                models.FieldCondition(
                    key=field_key, match=models.MatchText(text=capitalized)
                )
            )

        # If single condition, return it directly
        if len(conditions) == 1:
            return conditions[0]

        # Multiple conditions - use OR logic
        return models.Filter(should=conditions)


class BasicSearchStrategy(SearchStrategy):
    """Basic semantic search using hybrid vector similarity."""

    async def search(self, params: dict[str, Any]) -> list[models.ScoredPoint]:
        logger.info(f"Performing basic search for: '{params['query']}'")
        return await self.storage.client.query(
            collection_name=self.storage.collection_name,
            query_text=params["query"],
            query_filter=self._build_structured_filter(params),
            limit=params["limit"],
        )


class FilteredSearchStrategy(SearchStrategy):
    """Filtered search using structured query filters."""

    async def search(self, params: dict[str, Any]) -> list[models.ScoredPoint]:
        query = params["query"]
        filters = params["filters"]
        limit = params["limit"]

        logger.info(f"Performing filtered search with {len(filters)} filters")

        # Always use semantic query (even with empty string for consistent scoring)
        return await self.storage.client.query(
            collection_name=self.storage.collection_name,
            query_text=query,  # Use empty string if no query provided
            query_filter=self._build_structured_filter(params),
            limit=limit,
        )


class ByIdSearchStrategy(SearchStrategy):
    """Retrieves specific memory by UUID."""

    async def search(self, params: dict[str, Any]) -> list[models.ScoredPoint]:
        memory_id = params["query"]
        logger.info(f"Retrieving memory by ID: {memory_id}")

        points = await self.storage.client.retrieve(
            collection_name=self.storage.collection_name,
            ids=[memory_id],
            with_payload=True,
            with_vectors=False,
        )

        # Convert to ScoredPoint format for consistency
        scored_points = []
        for point in points:
            scored_point = models.ScoredPoint(
                id=point.id, version=0, score=1.0, payload=point.payload, vector=None
            )
            scored_points.append(scored_point)

        return scored_points
