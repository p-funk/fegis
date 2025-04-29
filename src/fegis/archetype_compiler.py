from __future__ import annotations

from datetime import datetime
from functools import lru_cache, cached_property
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union, Literal

import yaml
from pydantic import BaseModel, Field, create_model, field_validator

from .constants import TOOL_NAME, USE_TITLE, TIMESTAMP


# Core Pydantic Models
class ProcessModel(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}
    
    description: str
    illustrative_options: List[str] = []


class ProcessFieldModel(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}
    
    process: str
    required: bool = False
    default: Optional[str] = None


class FrameFieldModel(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}
    
    type: Optional[Union[Literal["List"], Literal["bool"], Literal["float"], str]] = None
    required: bool = False
    default: Optional[Any] = None

    @field_validator('type', mode='before')
    def validate_type(cls, v):
        if v is None:
            return v
        return str(v)


class ToolModel(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}
    
    description: Optional[str] = ""
    processes: Optional[Dict[str, ProcessFieldModel]] = None
    frames: Optional[Dict[str, Optional[FrameFieldModel]]] = None

    @field_validator('frames', mode='before')
    def validate_relata(cls, v):
        if v is None:
            return None
        result = {}
        for key, value in v.items():
            result[key] = value if value is not None else FrameFieldModel()
        return result


class Archetype(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}
    
    version: str
    title: str
    priming_prompt: Optional[str] = ""
    processes: Dict[str, ProcessModel]
    tools: Dict[str, ToolModel]

    @field_validator('version', mode='before')
    def validate_version(cls, v):
        return str(v)


class ArchetypeDefinition:
    """Loads and introspects YAML archetype definitions."""

    def __init__(self, yaml_path: Path | str):
        raw = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
        self._preprocess_raw_data(raw)
        self.archetype = Archetype.model_validate(raw)

    def _preprocess_raw_data(self, raw: Dict[str, Any]) -> None:
        """Normalize shorthand process syntax to process field model."""
        if "tools" not in raw:
            return

        for tool_data in raw["tools"].values():
            processes = tool_data.get("processes", {})
            if not isinstance(processes, dict):
                continue
            updated_processes = {}
            for name, val in processes.items():
                if isinstance(val, dict) and "process" in val:
                    updated_processes[name] = val
                else:
                    updated_processes[name] = {
                        "process": name,
                        "default": val,
                        "required": False
                    }
            tool_data["processes"] = updated_processes

    @cached_property
    def _tool_metadata(self) -> Dict[str, Dict[str, Any]]:
        md: Dict[str, Dict[str, Any]] = {}
        for name, tool in self.archetype.tools.items():
            relata: Set[str] = {
                fname
                for fname, f in (tool.frames or {}).items()
                if f and f.type in ("List", "Boolean", "float")
            }
            md[name] = {
                "content_field": f"{name.lower()}_content",
                "use_title_field": f"{name.lower()}_title",
                "frame_fields": relata,
            }
        return md

    def tools(self) -> List[str]:
        return list(self.archetype.tools)

    def tool(self, name: str) -> ToolModel:
        return self.archetype.tools[name]

    def processes(self) -> Dict[str, ProcessModel]:
        return self.archetype.processes or {}

    def illustrative_options(self, process: str) -> List[str]:
        return self.processes().get(process, ProcessModel(description="", illustrative_options=[])).illustrative_options

    def content_field(self, tool: str) -> str:
        return self._tool_metadata[tool]["content_field"]

    def use_title_field(self, tool: str) -> str:
        return self._tool_metadata[tool]["use_title_field"]

    def frame_fields(self, tool: str) -> Set[str]:
        return self._tool_metadata[tool]["frame_fields"]


class ArchetypeModelGenerator:
    """Generates runtime Pydantic models for archetype tools."""

    @staticmethod
    @lru_cache(maxsize=128)
    def create(schema: ArchetypeDefinition, tool_name: str) -> Type[BaseModel]:
        tool = schema.tool(tool_name)
        defs: Dict[str, Tuple[Any, Field]] = {}

        # Core fields
        title, content = schema.use_title_field(tool_name), schema.content_field(tool_name)
        defs[title] = (str, Field(...))
        defs[content] = (str, Field(...))

        # Facet fields
        for fname, f in (tool.processes or {}).items():
            process_model = schema.processes().get(f.process)
            typ = Optional[str] if not f.required and f.default is None else str
            default = ... if f.required else f.default
            defs[fname] = (
                typ,
                Field(
                    default,
                    description=process_model.description if process_model else "",
                    json_schema_extra={
                        "process": f.process,
                        "illustrative_options": schema.illustrative_options(f.process),
                    },
                ),
            )

        # Relata fields
        for fname, r in (tool.frames or {}).items():
            if r is None:
                typ = Optional[str]
                default = None
            elif r.type == "List":
                typ = Optional[List[str]] if not r.required and r.default is None else List[str]
                default = ... if r.required else r.default or []
            elif r.type == "bool":
                typ = bool
                default = ... if r.required else r.default if r.default is not None else False
            elif r.type == "float":
                typ = float
                default = ... if r.required else r.default if r.default is not None else 0.0
            else:
                typ = Optional[str] if not r.required and r.default is None else str
                default = ... if r.required else r.default
            defs[fname] = (typ, Field(default))

        return create_model(f"{tool_name}Input", **defs)


class ArtifactFieldMapper:
    """Converts validated inputs into storable content and metadata."""

    @staticmethod
    def to_storage(schema: ArchetypeDefinition, tool: str, data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        content = data[schema.content_field(tool)]
        title = data[schema.use_title_field(tool)]

        # Get all global processes
        all_processes = set(schema.processes().keys())

        # Get all frames field names from the tool definition
        mode_obj = schema.tool(tool)
        all_relata = set(mode_obj.frames.keys() if mode_obj.frames else {})

        meta: Dict[str, Any] = {
            TOOL_NAME: tool,
            TIMESTAMP: datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            USE_TITLE: title,
            "processes": {k: data[k] for k in all_processes if k in data},
            "frames": {k: data[k] for k in all_relata if k in data},
        }
        return content, meta
