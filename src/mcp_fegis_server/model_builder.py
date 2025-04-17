"""
Structured model builder module for FEGIS.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import yaml
from pydantic import BaseModel, Field, create_model

from .constants import TYPE_MAP, MODE_FIELD, ARTIFACT_ID_FIELD, CREATED_AT_FIELD, TITLE_FIELD


class ArchetypeDefinition:
    """Holds the YAML config and exposes convenient cached properties."""

    def __init__(self, yaml_path: str):
        # Simplified to just load a single YAML file
        self.yaml_path = Path(yaml_path)
        self.raw = self._load_file()

    @cached_property
    def modes(self) -> list[str]:
        return list(self.raw.get("modes", {}))

    @cached_property
    def facets(self) -> dict:
        return self.raw.get("facets", {})

    @cached_property
    def relata_fields(self) -> set[str]:
        """
        Return the set of field names whose type is `List[str]`
        across every mode in the archetype.
        """
        names: set[str] = set()

        # loop over each mode *name* and its schema at the same time
        for mode_name, mode_schema in self.raw.get("modes", {}).items():
            for field_name, spec in mode_schema.get("fields", {}).items():
                if spec.get("type") == "List[str]":
                    names.add(field_name)

        return names

    def mode_schema(self, name: str) -> dict:
        return self.raw["modes"][name]

    def facet_schema(self, name: str) -> dict:
        return self.raw["facets"].get(name, {})

    def content_field(self, mode: str) -> Optional[str]:
        explicit = self.mode_schema(mode).get("content_field")
        if explicit:
            return explicit
        for fname in self.mode_schema(mode).get("fields", {}):
            if fname.endswith("_content"):
                return fname
        return None

    def description(self, mode: str) -> str:
        return self.mode_schema(mode).get("description", f"Process {mode}")

    def _load_file(self) -> dict:
        """Load a single YAML file."""
        with self.yaml_path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)


@dataclass(frozen=True, slots=True)
class FieldDef:
    name: str
    py_type: type
    required: bool
    default: Any
    facet: Optional[str]
    is_relata: bool


def iter_field_defs(mode_schema: dict) -> list[FieldDef]:
    out: list[FieldDef] = []
    for name, spec in mode_schema.get("fields", {}).items():
        out.append(
            FieldDef(
                name=name,
                py_type=TYPE_MAP.get(spec.get("type", "str"), Any),
                required=spec.get("required", False),
                default=None if spec.get("default") == "now()" else spec.get("default"),
                facet=spec.get("facet"),
                is_relata=spec.get("type") == "List[str]",
            )
        )
    return out


# ─────────────────────────── model + mapper ────────────────────────────

class ArchetypeModelGenerator:
    """Creates a Pydantic model from a mode schema.🗺️"""

    @staticmethod
    def create(schema: ArchetypeDefinition, mode: str) -> type[BaseModel]:
        fields = {}
        for f in iter_field_defs(schema.mode_schema(mode)):
            extra = {}
            if f.facet:
                extra["facet"] = f.facet
                examples = schema.facet_schema(f.facet).get("facet_examples")
                if examples:
                    extra["facet_examples"] = examples

            # Handle optional string fields with no default value
            field_type = f.py_type
            if not f.required and f.default is None and f.py_type is str:
                field_type = Optional[str]

            fields[f.name] = (
                field_type,
                Field(
                    ... if f.required else f.default,
                    description=schema.facet_schema(f.facet).get("description", "") if f.facet else "",
                    json_schema_extra=extra or None,
                ),
            )
        return create_model(f"{mode}Input", **fields)

class ArtifactFieldMapper:
    """Transforms validated input ➜ (content, metadata) for Qdrant."""

    @staticmethod
    def to_storage(schema: ArchetypeDefinition, mode: str, data: dict) -> Tuple[str, dict]:
        content_key = schema.content_field(mode)
        if not content_key:
            raise ValueError(f"No content_field defined or inferred for mode '{mode}'")
        content = data[content_key]

        meta: dict[str, Any] = {
            MODE_FIELD: mode,
            "provenance": {
                # Use the constants but strip the provenance. prefix
                ARTIFACT_ID_FIELD.split(".")[1]: str(uuid.uuid4()),
                CREATED_AT_FIELD.split(".")[1]: datetime.now().isoformat(),
            },
            "facets": {},
            "relata": {},
        }

        # title support
        for key, val in data.items():
            if key.endswith("_title"):
                meta[TITLE_FIELD] = val
                break

        for fd in iter_field_defs(schema.mode_schema(mode)):
            if fd.name in (content_key, "title"):
                continue
            val = data.get(fd.name)
            if fd.facet:
                meta["facets"][fd.name] = val
            elif fd.is_relata:
                meta["relata"][fd.name] = val

        return content, meta