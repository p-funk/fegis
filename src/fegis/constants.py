"""
Project-wide schema definitions

This module contains constant definitions used throughout the Fegis project:

1. TYPE/TYPE_ALIASES: Type mapping for schema validation and conversion
2. SPECIAL_TYPES: Non-string type identifiers for special handling
3. INDEX: Database index type mapping for Qdrant
4. DEFAULTS: Default values for various parameters
5. FORMAT: Date and other formatting strings
6. ERROR: Standard error message templates

Note: String literals are preferred over constants for stable API fields,
query parameters, and tool names where the values are unlikely to change
and already self-documenting.
"""
from typing import List
from qdrant_client.http.models import PayloadSchemaType

# No field name constants - direct string literals are cleaner for these stable field names

# Type mapping for dynamic model generation - normalized to lowercase for consistency
TYPE = {
    # Format: type_name: (python_type, default_empty_value)
    "list": (List[str], []),
    "bool": (bool, False),
    "number": (float, 0.0),
    "float": (float, 0.0),
    None: (str, "")  # Default for unspecified types
}

# Normalized aliases mapping to canonical types
TYPE_ALIASES = {
    "List": "list",
    "Bool": "bool",
    "Boolean": "bool",
    "Number": "number",
    "Float": "float"
}

# Set of special types requiring specific handling (non-string types)
SPECIAL_TYPES = {"list", "bool", "number", "float"}

# Index mapping for Qdrant schema
INDEX = {
    "keyword": PayloadSchemaType.KEYWORD,
    "text": PayloadSchemaType.TEXT,
    "int": PayloadSchemaType.INTEGER,
    "float": PayloadSchemaType.FLOAT,
    "bool": PayloadSchemaType.BOOL,
    "date": PayloadSchemaType.DATETIME,
    "uuid": PayloadSchemaType.UUID
}

# No response field constants - direct string literals are cleaner for these stable API fields

# No query parameter constants - direct string literals are cleaner for stable API parameters

# Default values for parameters
DEFAULTS = {
    # Search parameters
    "limit": 3,
    "min_limit": 1,
    "max_limit": 10,
    "min_ef": 16,
    "max_ef": 512
}

# Format string constants
FORMAT = {
    "timestamp": "%B %d, %Y at %I:%M %p"
}

# No tool name constants - direct string literals are cleaner for these stable identifiers

# Error message templates
ERROR = {
    "search_failed": "Search failed: {}",
    "not_found": "Not found"
}