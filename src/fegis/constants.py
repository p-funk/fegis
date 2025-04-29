"""
Project‑wide “magic strings” live here..
"""
from qdrant_client.http.models import PayloadSchemaType

# Qdrant payload fields
TOOL_NAME         = "tool"
USE_TITLE    = "title"
TIMESTAMP         = "timestamp"

# YAML ➜ Python type map
TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "List[str]": list[str],
}
INDEX_TYPE_MAP = {
    "keyword": PayloadSchemaType.KEYWORD,
    "text": PayloadSchemaType.TEXT,
    "int": PayloadSchemaType.INTEGER,
    "float": PayloadSchemaType.FLOAT,
    "uuid": PayloadSchemaType.UUID,
}
