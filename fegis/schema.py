"""Schema generation for converting YAML archetypes into MCP-compliant tool definitions.

This module provides the core functionality for transforming structured YAML archetype
configurations into validated MCP tool schemas with proper type checking and runtime
validation via Pydantic models.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeAlias

import yaml
from loguru import logger

# Type aliases for better IDE intelligence
ArchetypeData: TypeAlias = dict[str, Any]
ToolSchema: TypeAlias = dict[str, Any]
ToolSchemas: TypeAlias = dict[str, ToolSchema]
ParameterDefinition: TypeAlias = dict[str, Any]
ParameterDefinitions: TypeAlias = dict[str, ParameterDefinition]
ValidationResult: TypeAlias = tuple[dict[str, Any], list[str]]

__all__ = [
    "load_archetype",
    "create_tool_schemas",
    "ArchetypeData",
    "ToolSchema",
    "ToolSchemas",
    "ParameterDefinition",
    "ParameterDefinitions",
    "ValidationResult",
]

# --- Schema Constants ---
KEY_PARAMETERS = "parameters"
KEY_TOOLS = "tools"
KEY_DESCRIPTION = "description"
KEY_EXAMPLES = "examples"
KEY_TYPE = "type"
KEY_REQUIRED = "required"
KEY_DEFAULT = "default"
KEY_INPUT_SCHEMA = "inputSchema"
KEY_PROPERTIES = "properties"
KEY_ADDITIONAL_PROPERTIES = "additionalProperties"
KEY_X_REQUIRED = "x-required"
KEY_NAME = "name"
KEY_STRING = "string"

# --- Standard Fields Configuration ---
STANDARD_FIELDS = ["Title", "Content", "Context"]
STANDARD_FIELD_DESCRIPTIONS = {
    "Title": "A clear, descriptive title for this structured response",
    "Content": "The main content or output of the prompt execution",
    "Context": "Relevant context that informed this response",
}


def load_archetype(path: str) -> ArchetypeData:
    """Load and validate a YAML archetype from file.

    Args:
        path: File system path to the YAML archetype file

    Returns:
        Parsed archetype data as a dictionary

    Raises:
        FileNotFoundError: If the archetype file doesn't exist
        yaml.YAMLError: If the YAML file is malformed
    """
    logger.info(f"Loading archetype from: {path}")
    filepath = Path(path)

    if not filepath.exists():
        raise FileNotFoundError(f"Archetype file not found: {path}")

    with open(filepath, encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_tool_schemas(archetype_data: ArchetypeData) -> ToolSchemas:
    """Create MCP-compliant tool schemas from YAML archetype definition.

    Args:
        archetype_data: Parsed YAML archetype containing tools and parameters

    Returns:
        Dictionary mapping tool names to their MCP schema definitions
    """
    tool_schemas = {}
    global_parameter_definitions = archetype_data.get(KEY_PARAMETERS, {})
    archetype_tools = archetype_data.get(KEY_TOOLS, {})

    logger.info(f"Generating tool schemas for {len(archetype_tools)} tools")

    for tool_name, tool_definition in archetype_tools.items():
        schema_properties = {}
        required_fields = []

        # Standard Field Integration - Every tool inherits these
        for standard_field_name in STANDARD_FIELDS:
            schema_properties[standard_field_name] = {
                KEY_TYPE: KEY_STRING,
                KEY_DESCRIPTION: STANDARD_FIELD_DESCRIPTIONS.get(
                    standard_field_name, ""
                ),
                KEY_X_REQUIRED: True,
            }
            required_fields.append(standard_field_name)

        # Three-Layer Parameter Architecture
        tool_specific_params = tool_definition.get(KEY_PARAMETERS, {})
        parameter_properties, parameter_required_fields = _process_parameters(
            tool_specific_params, global_parameter_definitions, tool_name
        )
        schema_properties.update(parameter_properties)
        required_fields.extend(parameter_required_fields)

        # Structured Output Frames - Prompt scaffolding
        output_frames = tool_definition.get("frames", {})
        frame_properties, frame_required_fields = _process_frames(
            output_frames, tool_name
        )
        schema_properties.update(frame_properties)
        required_fields.extend(frame_required_fields)

        # Assemble final schema
        tool_schemas[tool_name] = {
            KEY_NAME: tool_name,
            KEY_DESCRIPTION: tool_definition.get(KEY_DESCRIPTION, f"Tool: {tool_name}"),
            KEY_INPUT_SCHEMA: {
                KEY_TYPE: "object",
                KEY_PROPERTIES: schema_properties,
                KEY_REQUIRED: sorted(set(required_fields)),
                KEY_ADDITIONAL_PROPERTIES: False,
            },
        }

    return tool_schemas


def _process_parameters(
    tool_specific_params: ParameterDefinitions,
    global_parameter_definitions: ParameterDefinitions,
    tool_name: str,
) -> ValidationResult:
    """Process parameters with three-layer binding: open, defaulted, or hidden.

    Args:
        tool_specific_params: Tool-specific parameter configurations
        global_parameter_definitions: Global parameter pool definitions
        tool_name: Name of the tool being processed (for logging)

    Returns:
        Tuple of (parameter properties dict, required parameter names list)
    """
    parameter_properties = {}
    required_parameters = []

    for param_name, param_binding_value in tool_specific_params.items():
        if param_name not in global_parameter_definitions:
            logger.warning(
                f"Parameter '{param_name}' in tool '{tool_name}' not in global pool. Skipping."
            )
            continue

        global_param_definition = global_parameter_definitions[param_name]
        parameter_property = {
            KEY_TYPE: KEY_STRING,
            KEY_DESCRIPTION: global_param_definition.get(KEY_DESCRIPTION, ""),
        }

        # Add semantic anchors (examples as guidance, not constraints)
        if KEY_EXAMPLES in global_param_definition:
            parameter_property[KEY_EXAMPLES] = global_param_definition[KEY_EXAMPLES]

        # Three-layer parameter binding: open, defaulted, or hidden
        if param_binding_value is None:
            # Open: user must provide value
            parameter_property[KEY_X_REQUIRED] = True
            required_parameters.append(param_name)
        elif isinstance(param_binding_value, str) and param_binding_value:
            # Defaulted: has default but visible to user
            parameter_property[KEY_DEFAULT] = param_binding_value
            parameter_property[KEY_X_REQUIRED] = True
            required_parameters.append(param_name)
        # Hidden: not exposed in schema (skip)
        else:
            continue

        parameter_properties[param_name] = parameter_property

    return parameter_properties, required_parameters


def _process_frames(output_frames: dict[str, Any], tool_name: str) -> ValidationResult:
    """Process output frames for structured prompt scaffolding.

    Args:
        output_frames: Frame definitions from the tool configuration
        tool_name: Name of the tool being processed (for logging)

    Returns:
        Tuple of (frame properties dict, required frame names list)
    """
    frame_properties = {}
    required_frames = []

    # Complete type mapping for all JSON Schema types
    type_mapping = {
        "list": "array",
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "object": "object",
    }

    for frame_name, frame_definition in output_frames.items():
        # Handle cases where frame_definition might be None or empty
        frame_definition = (
            frame_definition if isinstance(frame_definition, dict) else {}
        )

        frame_type = str(frame_definition.get(KEY_TYPE, KEY_STRING)).lower()
        is_required_frame = frame_definition.get(KEY_REQUIRED, False)

        frame_property = {"type": type_mapping.get(frame_type, frame_type)}

        # Structured Frame Design Patterns - Only x-required is needed
        if is_required_frame:
            frame_property[KEY_X_REQUIRED] = True
            required_frames.append(frame_name)

        frame_properties[frame_name] = frame_property

    return frame_properties, required_frames
