from __future__ import annotations

from datetime import datetime
from functools import lru_cache, cached_property
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union, Literal

import yaml
from pydantic import BaseModel, Field, create_model, field_validator

from .constants import TYPE, TYPE_ALIASES, FORMAT, SPECIAL_TYPES


# Core Pydantic Models
class ParameterModel(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    description: str
    example_values: List[str] = []


class ParameterFieldModel(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    parameter: str
    required: bool = False
    default: Optional[str] = None


class FrameFieldModel(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    type: Optional[Union[Literal["List"], Literal["bool"], Literal["float"], str]] = None
    required: bool = False
    default: Optional[Any] = None

    @field_validator('type', mode='before')
    def validate_type(cls, v):
        return v if v is None else str(v)


class ToolModel(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    description: Optional[str] = ""
    parameters: Optional[Dict[str, ParameterFieldModel]] = None
    frames: Optional[Dict[str, Optional[FrameFieldModel]]] = None

    @field_validator('frames', mode='before')
    def validate_frames(cls, v):
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
    archetype_context: Optional[str] = ""
    parameters: Dict[str, ParameterModel]
    tools: Dict[str, ToolModel]

    @field_validator('version', mode='before')
    def validate_version(cls, v):
        return str(v)


class ArchetypeDefinition:
    """🗺️ Compiles declarative YAML Archetypes into structured interaction models

    Architecture components:
    - Parameters: Named semantic dimensions (e.g. Clarity, Vibe) that parameterize interactions
    - Tools: Structured interaction interfaces with defined parameter contexts and outputs
    - Frames: JSON-schema compliant output structures enforcing data validation patterns
    - Traces: Runtime representations suitable for vector embedding and semantic retrieval

    The compiler normalizes shorthand syntax, validates against Pydantic models,
    and provides caching and lookup functionality.
    """

    def __init__(self, yaml_path: Path | str):
        """Initialize an ArchetypeDefinition from a YAML file path.

        Args:
            yaml_path: Path to the YAML file containing the archetype definition
        """
        # Load and parse the YAML file
        raw = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
        # Convert shorthand parameter syntax to full format
        self._preprocess_raw_data(raw)
        # Validate the raw data against the Archetype model
        self.archetype = Archetype.model_validate(raw)

    def _preprocess_raw_data(self, raw: Dict[str, Any]) -> None:
        """Normalize shorthand parameter syntax to parameter field model.

        This method handles two syntaxes for parameter definitions:
        1. Shorthand: ParameterName: "default_value"
        2. Shorthand empty: ParameterName: (empty)
        3. Full: ParameterName: { parameter: "Name", default: "value", required: bool }

        All forms are converted to the full syntax for consistent processing.

        Args:
            raw: The raw dictionary parsed from the YAML file
        """
        if "tools" not in raw:
            return

        for tool_data in raw["tools"].values():
            parameters = tool_data.get("parameters", {})
            if not isinstance(parameters, dict):
                continue

            # Use dictionary comprehension for cleaner code
            tool_data["parameters"] = {
                name: val if isinstance(val, dict) and "parameter" in val else {
                    "parameter": name,
                    "default": val,
                    "required": False
                }
                for name, val in parameters.items()
            }

    @cached_property
    def _tool_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Build and cache metadata for each tool.

        Computes:
        1. Field names for title and content
        2. Set of frame field names mapped to structured types (List, Boolean, Number)

        Returns:
            A dictionary mapping tool names to their metadata
        """
        # Use the centralized SPECIAL_TYPES from constants
        return {
            name: {
                "content_field": f"{name.lower()}_content",  # Convention for content field name
                "title_field": f"{name.lower()}_title",  # Convention for title field name
                "frame_fields": {
                    fname for fname, f in (tool.frames or {}).items()
                    if f and f.type in SPECIAL_TYPES
                }
            }
            for name, tool in self.archetype.tools.items()
        }

    def tools(self) -> List[str]:
        """Get the list of tool names defined in the archetype.

        Returns:
            List of tool names
        """
        return list(self.archetype.tools)

    def tool(self, name: str) -> ToolModel:
        """Get a specific tool by name.

        Args:
            name: The name of the tool to retrieve

        Returns:
            The ToolModel for the specified tool
        """
        return self.archetype.tools[name]

    def parameters(self) -> Dict[str, ParameterModel]:
        """Get all parameters defined in the archetype.

        Returns:
            Dictionary mapping parameter names to their ParameterModel
        """
        return self.archetype.parameters or {}

    def example_values(self, parameter: str) -> List[str]:
        """Get the example_values options for a specific parameter.

        These options represent potential values for the parameter
        and can be used for UI hints, validation, etc.

        Args:
            parameter: Name of the parameter

        Returns:
            List of example_values strings, or empty list if not found
        """
        return self.parameters().get(parameter, ParameterModel(description="", example_values=[])).example_values

    def content_field(self, tool: str) -> str:
        """Get the content field name for a specific tool.

        Args:
            tool: The name of the tool

        Returns:
            Field name for the tool's content
        """
        return self._tool_metadata[tool]["content_field"]

    def title_field(self, tool: str) -> str:
        """Get the use title field name for a specific tool.

        Args:
            tool: The name of the tool

        Returns:
            Field name for the tool's use title
        """
        return self._tool_metadata[tool]["title_field"]

    def frame_fields(self, tool: str) -> Set[str]:
        """Get the set of frame field names with non-string types for a tool.

        Args:
            tool: The name of the tool

        Returns:
            Set of frame field names with special types (List, Boolean, float)
        """
        return self._tool_metadata[tool]["frame_fields"]


class ArchetypeModelGenerator:
    """🗺️ Runtime Pydantic model factory for schema-validated tool invocations.

    Dynamically generates strongly-typed Pydantic models for each tool defined
    in an archetype, using LRU caching for performance. The generated models:

    1. Create proper field validation for each parameter and frame
    2. Handle type coercion and validation based on the YAML schema
    3. Apply default values and handling for optional fields
    4. Generate JSON Schema for external tools integration

    The cached models provide runtime validation to ensure all tool invocations
    conform to the defined schema before being processed and persisted.
    """
    @staticmethod
    @lru_cache(maxsize=128)
    def create(schema: ArchetypeDefinition, tool_name: str) -> Type[BaseModel]:
        tool = schema.tool(tool_name)
        defs: Dict[str, Tuple[Any, Field]] = {}

        title, content = schema.title_field(tool_name), schema.content_field(tool_name)
        defs[title] = (str, Field(...))
        defs[content] = (str, Field(...))

        # Process the parameter fields
        for fname, f in (tool.parameters or {}).items():
            parameter_model = schema.parameters().get(f.parameter)
            typ = Optional[str] if not f.required and f.default is None else str
            default = ... if f.required else f.default
            defs[fname] = (
                typ,
                Field(
                    default,
                    description=parameter_model.description if parameter_model else "",
                    json_schema_extra={
                        "parameter": f.parameter,
                        "example_values": schema.example_values(f.parameter),
                    },
                ),
            )

        # Process the frame fields
        for fname, r in (tool.frames or {}).items():
            # Normalize type name through aliases
            type_name = None
            if r and r.type:
                type_name = TYPE_ALIASES.get(r.type, r.type.lower() if isinstance(r.type, str) else None)

            # Get base type and default empty value
            base_type, default_empty = TYPE.get(type_name, TYPE[None])

            # Simplified optionality logic
            is_required = r and r.required
            default = ... if is_required else r.default if r and r.default is not None else default_empty
            typ = base_type if is_required else Optional[base_type]

            defs[fname] = (typ, Field(default))

        return create_model(f"{tool_name}Input", **defs)


class TraceFieldMapper:
    """🗺️ Maps tool invocations to trace records prepared for vector indexing and semantic retrieval.

    Normalizes heterogeneous tool outputs for persistent trace storage and semantic retrieval

    1. Content: The primary text used for semantic embedding and similarity search
    2. Metadata: Structured fields including:*+
       - Tool name and invocation timestamp
       - Title field for human-readable reference
       - Process values for semantic filtering (e.g., Clarity=translucent)
       - Frame data for structured factual retrieval and filtering

    This transformation enables both semantic similarity search and structured
    filtering/faceting in the Trace Archive, supporting a hybrid retrieval model.
    """

    @staticmethod
    def to_storage(schema: ArchetypeDefinition, tool: str, data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Convert validated tool input data to content and metadata.

        Args:
            schema: The archetype definition
            tool: The name of the tool
            data: The validated data from a tool input model

        Returns:
            A tuple of (content, metadata) where:
            - content: The main content string from the tool input
            - metadata: A dictionary containing tool metadata and all field values
        """
        # Extract field names
        content_field = schema.content_field(tool)
        title_field = schema.title_field(tool)

        # Get tool model once
        tool_model = schema.tool(tool)

        # Build metadata in one go
        meta = {
            "tool": tool,
            "timestamp": datetime.now().strftime(FORMAT["timestamp"]),
            "title": data[title_field],
            "parameters": {
                k: data[k] for k in schema.parameters().keys()
                if k in data
            },
            "frames": {
                k: data[k] for k in (tool_model.frames.keys() if tool_model.frames else set())
                if k in data
            }
        }

        return data[content_field], meta