"""Configuration-based result formatting with utility functions."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from ..models import Memory

# Constants for post-processing defaults
CONTENT_PREVIEW_LENGTH = 150

# Simple view configurations - all fields treated equally
RESULT_VIEWS = {
    "compact": {"fields": ["id", "title", "tool", "context", "score"]},
    "summary": {
        "fields": [
            "id",
            "title",
            "context",
            "tool",
            "score",
            "content_preview",
            "relative_time",
        ]
    },
    "graph": {
        "fields": [
            "id",
            "title",
            "preceding_memory_id",
            "session_id",
            "sequence_order",
            "tool",
            "relative_time",
            "memory_id",
            "timestamp",
            "score",
            "meta.agent_id",
            "meta.archetype_title",
        ]
    },
    "full": {
        "fields": [
            "id",
            "score",
            "title",
            "content",
            "context",
            "tool",
            "session_id",
            "sequence_order",
            "timestamp",
            "preceding_memory_id",
            "parameters",
            "frames",
            "meta",
            "memory_id",
        ]
    },
}


def format_memories(
    memories: list[Memory], view_name: str
) -> str:  # <-- Updated input type
    """Simple formatter that works directly with memory objects.

    Args:
        memories: List of memory objects
        view_name: Name of the view configuration to use

    Returns:
        JSON string of formatted results
    """
    view_config = RESULT_VIEWS.get(view_name)
    if not view_config:
        raise ValueError(
            f"Unknown view: {view_name}. Available: {list(RESULT_VIEWS.keys())}"
        )

    results = []

    for memory in memories:
        result = {}

        # Extract all requested fields (both direct and computed)
        for field in view_config["fields"]:
            if field == "content_preview":
                # Computed field: generate preview from content
                result[field] = format_content_preview(
                    memory.content, CONTENT_PREVIEW_LENGTH
                )
            elif field == "relative_time":
                # Computed field: generate relative time from timestamp
                result[field] = format_relative_time(memory.timestamp)
            elif "." in field:
                # Nested field: handle dot notation like "meta.agent_id"
                value = _get_nested_field(memory, field)
                result[field] = value
            else:
                # Direct field: get from memory object
                value = getattr(memory, field, None)
                # Handle different types for JSON serialization
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif hasattr(value, "model_dump"):
                    # Handle nested Pydantic models (like MemoryMeta)
                    value = value.model_dump()
                result[field] = value

        results.append(result)

    # Custom JSON encoder to handle datetime objects if any slip through
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)

    return json.dumps(results, indent=2, cls=DateTimeEncoder)


# Utility functions for formatting memory data


def _get_nested_field(obj: Memory, field_path: str) -> any:
    """Get nested field value using dot notation (e.g., 'meta.agent_id')."""
    parts = field_path.split(".")
    value = obj

    for part in parts:
        if hasattr(value, part):
            value = getattr(value, part)
        else:
            return None

    # Handle datetime and Pydantic model serialization
    if isinstance(value, datetime):
        return value.isoformat()
    elif hasattr(value, "model_dump"):
        return value.model_dump()

    return value


def format_relative_time(timestamp: datetime) -> str:
    """Convert timestamp to human-readable relative time."""
    now = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    diff = now - timestamp

    if diff.days > 0:
        if diff.days == 1:
            return "1 day ago"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"

    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60

    if hours > 0:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif minutes > 0:
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "just now"


def extract_summary(content: str, max_sentences: int = 1) -> str:
    """Extract first sentence(s) or key points from content."""
    if not content:
        return ""

    # Split by sentence boundaries
    sentences = re.split(r"[.!?]+", content)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        # Simple truncation fallback
        if len(content) <= 100:
            return content
        return content[:97] + "..."

    # Take first N sentences
    summary_sentences = sentences[:max_sentences]
    summary = ". ".join(summary_sentences)

    # Add period if it doesn't end with punctuation
    if summary and summary[-1] not in ".!?":
        summary += "."

    return summary


def format_content_preview(content: str, max_length: int = 150) -> str:
    """Create a preview of content suitable for display in search results."""
    if not content:
        return ""

    # Clean up whitespace
    cleaned_content = " ".join(content.split())

    # If cleaned content is short enough, return it directly
    if len(cleaned_content) <= max_length:
        return cleaned_content

    # Try to get a clean summary first
    preview = extract_summary(cleaned_content, max_sentences=2)

    # If summary is within limits, use it
    if len(preview) <= max_length:
        return preview

    # If summary is too long, truncate the summary intelligently
    return preview[: max_length - 3] + "..."
