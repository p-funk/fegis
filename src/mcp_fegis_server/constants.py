"""
Project‑wide “magic strings” live here..
"""

# Qdrant payload fields
MODE_FIELD         = "mode"
ARTIFACT_ID_FIELD  = "provenance.artifact_id"
CREATED_AT_FIELD   = "provenance.created_at"
TITLE_FIELD        = "title"

# YAML ➜ Python type map
TYPE_MAP = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "List[str]": list[str],
}
