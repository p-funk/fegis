"""Configuration-based result formatting with utility functions."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any

__all__ = [
    "ResultView",
    "format_memories",
    "format_relative_time",
    "format_content_preview",
]


class ResultView(str, Enum):
    """Available result view formats."""

    COMPACT = "compact"
    SUMMARY = "summary"
    GRAPH = "graph"
    FULL = "full"


CONTENT_PREVIEW_LENGTH = 150
RESULT_VIEWS = {
    "compact": {
        "fields": ["memory_id", "title", "tool", "context", "session_id", "score"]
    },
    "summary": {
        "fields": [
            "memory_id",
            "title",
            "context",
            "tool",
            "score",
            "content_preview",
            "relative_time",
            "session_id",
        ]
    },
    "graph": {
        "fields": [
            "memory_id",
            "title",
            "preceding_memory_id",
            "session_id",
            "sequence_order",
            "tool",
            "relative_time",
            "timestamp",
            "score",
            "meta.agent_id",
            "meta.archetype_title",
        ]
    },
    "full": {
        "fields": [
            "memory_id",
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
        ]
    },
}


def format_memories(
    memories: list[dict[str, Any]], view_name: str
) -> list[dict[str, Any]]:
    """Format memory dictionaries according to view configuration."""
    view_config = RESULT_VIEWS.get(view_name)
    if not view_config:
        raise ValueError(
            f"Unknown view: {view_name}. Available: {list(RESULT_VIEWS.keys())}"
        )

    return [
        {field: _get_field_value(memory, field) for field in view_config["fields"]}
        for memory in memories
    ]


def _get_field_value(memory: dict[str, Any], field: str) -> Any:
    """Get formatted value for a specific field."""
    field_processors = {
        "content_preview": lambda m: format_content_preview(
            m.get("content", ""), CONTENT_PREVIEW_LENGTH
        ),
        "relative_time": lambda m: _process_relative_time(m.get("timestamp", "")),
    }

    if field in field_processors:
        return field_processors[field](memory)
    elif "." in field:
        return _get_nested_field_dict(memory, field)
    else:
        value = memory.get(field)
        return value.isoformat() if isinstance(value, datetime) else value


def _process_relative_time(timestamp_str: str) -> str:
    """Process timestamp string into relative time."""
    if not timestamp_str:
        return ""
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return format_relative_time(timestamp)
    except (ValueError, AttributeError):
        return timestamp_str


def _get_nested_field_dict(obj: dict[str, Any], field_path: str) -> Any:
    """Get nested field value using dot notation from dictionary."""
    parts = field_path.split(".")
    value = obj

    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None

    if isinstance(value, datetime):
        return value.isoformat()

    return value


def format_relative_time(timestamp: datetime) -> str:
    """Convert timestamp to human-readable relative time."""
    now = datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)

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
