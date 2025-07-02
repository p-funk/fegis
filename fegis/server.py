"""Fegis MCP Server"""

import json
import sys
import uuid
from typing import Any

import anyio
import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions, ServerCapabilities

from .config import FegisConfig
from .schema import (
    STANDARD_FIELDS,
    ArchetypeData,
    ToolSchemas,
    create_tool_schemas,
    create_tool_validators,
    load_archetype,
)
from .search import SearchHandler
from .storage import Provenance, QdrantStorage

__all__ = ["main"]


def initialize_storage(config: FegisConfig) -> QdrantStorage:
    """Initialize and return the QdrantStorage instance."""
    try:
        storage = QdrantStorage(config)
        print("[OK] Storage setup complete", file=sys.stderr)
        return storage
    except Exception as e:
        print(f"[ERROR] Storage setup error: {e}", file=sys.stderr)
        sys.exit(1)


def load_archetype_tools(
    config: FegisConfig,
) -> tuple[ArchetypeData, ToolSchemas, dict[str, Any]]:
    """Load archetype data, create schemas, and compile validators."""
    try:
        archetype_data = load_archetype(config.archetype_path)
        tool_schemas = create_tool_schemas(archetype_data)
        tool_validators = create_tool_validators(tool_schemas)
        print(
            f"[OK] Loaded archetype: {archetype_data.get('title', 'Unknown')}",
            file=sys.stderr,
        )
        print(f"[OK] Generated {len(tool_schemas)} tool schemas", file=sys.stderr)
        return archetype_data, tool_schemas, tool_validators
    except Exception as e:
        print(f"[ERROR] Archetype loading error: {e}", file=sys.stderr)
        sys.exit(1)


def return_tool_error(error_msg: str) -> str:
    """Clean up validation error messages for better AI understanding."""
    if "Cannot convert undefined or null to object" in error_msg:
        return "One or more required fields are missing or null. Please provide all required frame fields with valid values."
    elif "undefined" in error_msg or "null" in error_msg:
        return f"Invalid field value: {error_msg}. Please provide valid values for all required fields."
    else:
        return error_msg.replace("data.", "").replace("data ", "")


async def handle_archetype_tool(
    name: str,
    arguments: dict,
    archetype_data: ArchetypeData,
    tool_validators: dict[str, Any],
    storage: QdrantStorage,
    server_session_id: str,
) -> dict:
    """Execute archetype tool, validate inputs, and store as memory."""
    tool_definition = archetype_data["tools"][name]

    tool_parameter_keys = set(tool_definition.get("parameters", {}).keys())
    all_parameter_keys = tool_parameter_keys | set(STANDARD_FIELDS)
    parameters = {k: v for k, v in arguments.items() if k in all_parameter_keys}

    frame_field_keys = set(tool_definition.get("frames", {}).keys())
    frames = {k: v for k, v in arguments.items() if k in frame_field_keys}

    complete_response = {**parameters, **frames}
    try:
        tool_validators[name](complete_response)
    except Exception as validation_error:
        error_msg = return_tool_error(str(validation_error))
        raise ValueError(
            f"Tool validation failed: {error_msg}\nPlease correct the errors and retry."
        ) from validation_error

    preceding_memory_id, sequence_order = await storage.get_last_memory_for_session(
        server_session_id
    )
    tool_provenance: Provenance = {
        "session_id": server_session_id,
        "sequence_order": sequence_order,
        "preceding_memory_id": preceding_memory_id,
    }

    memory_id = await storage.store_invocation(
        tool_name=name,
        parameters=parameters,
        frames=frames,
        archetype=archetype_data,
        provenance=tool_provenance,
    )

    return {
        "message": f"'{name}' stored with memory_id: {memory_id}",
    }


async def handle_search_tool(arguments: dict, search_handler: SearchHandler) -> dict:
    """Execute search tool and return formatted results."""
    search_args = {
        "query": arguments.get("query", ""),
        "limit": arguments.get("limit", 3),
        "search_type": arguments.get("search_type", "basic"),
        "detail": arguments.get("detail", "summary"),
        "score_threshold": arguments.get("score_threshold", 0.4),
        "filters": arguments.get("filters", []),
    }
    found_memories = await search_handler.search(search_args)

    from .search.formatters import format_memories

    formatted_results = format_memories(found_memories, search_args["detail"])
    return {"search_results": formatted_results}


def main() -> int:
    """Main entry point for Fegis MCP server."""
    try:
        config = FegisConfig.from_env()
        print(f"[OK] Loaded config for agent: {config.agent_id}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}", file=sys.stderr)
        return 1

    storage = initialize_storage(config)
    archetype_data, tool_schemas, tool_validators = load_archetype_tools(config)

    mcp_server = Server(config.server_name)
    search_handler = SearchHandler(storage)
    server_session_id = str(uuid.uuid4())
    print(f"[OK] Server session: {server_session_id}", file=sys.stderr)

    @mcp_server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """Return all available archetype and search tools."""
        tools = []
        for tool_name, schema in tool_schemas.items():
            tool_definition = archetype_data["tools"][tool_name]
            tools.append(
                types.Tool(
                    name=tool_name,
                    description=tool_definition.get("description", ""),
                    inputSchema=schema["inputSchema"],
                )
            )

        search_tool_config = config.search_tool_schema
        tools.append(
            types.Tool(
                name=search_tool_config["name"],
                description=search_tool_config["description"],
                inputSchema=search_tool_config["inputSchema"],
            )
        )
        return tools

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        """Route tool calls to appropriate handlers and return JSON responses."""
        try:
            if name == config.search_tool_schema["name"]:
                result = await handle_search_tool(arguments, search_handler)
            elif name in archetype_data["tools"]:
                result = await handle_archetype_tool(
                    name,
                    arguments,
                    archetype_data,
                    tool_validators,
                    storage,
                    server_session_id,
                )
            else:
                raise ValueError(f"Unknown tool: {name}")

            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        except (ValueError, TypeError) as e:
            error_result = {"error": str(e), "type": type(e).__name__}
            return [
                types.TextContent(type="text", text=json.dumps(error_result, indent=2))
            ]
        except Exception as e:
            error_result = {"error": f"An unexpected error occurred: {e}", "type": type(e).__name__}
            return [
                types.TextContent(type="text", text=json.dumps(error_result, indent=2))
            ]

    if config.transport == "stdio":

        async def run_server() -> None:
            try:
                await storage.initialize()
                print("[OK] Storage initialized", file=sys.stderr)
                print(
                    "[READY] Fegis MCP server startup complete - ready for connections",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"[ERROR] Storage initialization failed: {e}", file=sys.stderr)
                sys.exit(1)

            init_options = InitializationOptions(
                server_name=config.server_name,
                server_version=config.fegis_version,
                capabilities=ServerCapabilities(tools={}),
            )

            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                await mcp_server.run(read_stream, write_stream, init_options)

        anyio.run(run_server)

    return 0


if __name__ == "__main__":
    main()

