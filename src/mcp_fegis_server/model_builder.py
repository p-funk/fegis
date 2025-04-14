"""
Structured model builder module for FEGIS.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Type, Any, List, Optional, Tuple

import yaml
from pydantic import BaseModel, create_model, Field


class ArchetypeDefinition:
    """Container for the parsed YAML archetype with accessor methods for modes and facets."""

    def __init__(self, yaml_path: str):
        self.yaml_path = Path(yaml_path)
        self.raw_schema = self._load_yaml()

    def _load_yaml(self) -> dict:
        with self.yaml_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_mode_names(self) -> List[str]:
        return list(self.raw_schema.get("modes", {}).keys())

    def get_mode_schema(self, mode_name: str) -> dict:
        return self.raw_schema.get("modes", {}).get(mode_name, {})

    def get_facet_schema(self, facet_name: str) -> dict:
        return self.raw_schema.get("facets", {}).get(facet_name, {})

    def get_content_field(self, mode_name: str) -> Optional[str]:
        # First try to get explicitly defined content_field
        content_field = self.get_mode_schema(mode_name).get("content_field")

        # If not found, try to infer it from field names
        if not content_field:
            fields = self.get_mode_schema(mode_name).get("fields", {})
            # Look for a field with name ending in "_content"
            for field_name in fields:
                if field_name.endswith("_content"):
                    return field_name

        return content_field

    def get_description(self, mode_name: str) -> str:
        return self.get_mode_schema(mode_name).get("description", f"Process {mode_name}")

    def get_field_schema(self, mode_name: str, field_name: str) -> dict:
        return self.get_mode_schema(mode_name).get("fields", {}).get(field_name, {})


class ArchetypeModelGenerator:
    """Generates Pydantic models from an ArchetypeDefinition.🗺️"""

    TYPE_MAP = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "List[str]": List[str],
    }

    @classmethod
    def create_model_for_mode(cls, schema: ArchetypeDefinition, mode_name: str) -> Type[BaseModel]:
        mode_schema = schema.get_mode_schema(mode_name)
        field_schemas = mode_schema.get("fields", {})

        field_definitions = {}

        for field_name, field_schema in field_schemas.items():
            field_type = cls.TYPE_MAP.get(field_schema.get("type", "str"), Any)

            if field_schema.get("required", False):
                default = ...
            else:
                # Handle the case where default is explicitly set to null
                if "default" in field_schema and field_schema["default"] is None:
                    # Treat explicit null the same as no default
                    default = None
                else:
                    default = field_schema.get("default", None)

            if default == "now()":
                default = None

            # Build metadata
            facet_name = field_schema.get("facet")
            if facet_name:
                facet_schema = schema.get_facet_schema(facet_name)
                description = facet_schema.get("description", f"Property of type {facet_name}")
            else:
                description = field_schema.get("description", "")

            # Create extra schema metadata (using json_schema_extra to be compatible with Pydantic V2+)
            extra_schema = {}
            if facet_name:
                extra_schema["facet"] = facet_name
                facet_schema = schema.get_facet_schema(facet_name)
                if facet_schema and "facet_examples" in facet_schema:
                    extra_schema["facet_examples"] = facet_schema["facet_examples"]

            # Create the field with proper Pydantic V2+ structure
            field_definitions[field_name] = (
                field_type, 
                Field(
                    default,
                    description=description,
                    json_schema_extra=extra_schema if extra_schema else None
                )
            )

        return create_model(f"{mode_name}Input", **field_definitions)


class ArtifactFieldMapper:
    """Maps between archetypal data and the Fegis-compatible artifact format."""

    @staticmethod
    def to_storage_format(schema: ArchetypeDefinition, mode_name: str, data: dict) -> Tuple[str, dict]:
        content_field = schema.get_content_field(mode_name)
        if not content_field or content_field not in data:
            raise ValueError(f"Missing content field '{content_field}' for mode '{mode_name}'")

        content = data[content_field]

        metadata = {
            "mode": mode_name,
            "provenance": {
                "memory_id": str(uuid.uuid4()),
                "created_at": datetime.now().isoformat()
            },
            "facets": {},
            "relata": {},
        }

        for field_name, value in data.items():
            if field_name == content_field:
                continue

            field_schema = schema.get_field_schema(mode_name, field_name)

            if "facet" in field_schema:
                metadata["facets"][field_name] = value
            elif field_schema.get("type") == "List[str]":
                metadata["relata"][field_name] = value
            elif field_name.endswith("_title"):
                metadata["title"] = value

        return content, metadata
