"""Fegis MCP Server"""

import json
import sys
import uuid

import anyio
import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions, ServerCapabilities

from .config import FegisConfig
from .schema import (
    STANDARD_FIELDS,
    create_tool_schemas,
    create_tool_validators,
    load_archetype,
)
from .search import SearchHandler
from .storage import QdrantStorage


def main() -> int:
    """Main entry point for Fegis MCP server."""

    # Load configuration
    try:
        config = FegisConfig.from_env()
        print(f"[OK] Loaded config for agent: {config.agent_id}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}", file=sys.stderr)
        return 1

    # Initialize storage early (slow operations: model downloads, Qdrant connection)
    try:
        storage = QdrantStorage(config)
    except Exception as e:
        print(f"[ERROR] Storage setup error: {e}", file=sys.stderr)
        return 1

    # Load archetype and generate schemas
    try:
        archetype_data = load_archetype(config.archetype_path)
        tool_schemas = create_tool_schemas(archetype_data)
        tool_validators = create_tool_validators(tool_schemas)
        print(
            f"[OK] Loaded archetype: {archetype_data.get('title', 'Unknown')}",
            file=sys.stderr,
        )
        print(f"[OK] Generated {len(tool_schemas)} tool schemas", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Archetype loading error: {e}", file=sys.stderr)
        return 1

    # Create MCP server instance
    mcp_server = Server(config.server_name)

    # Generate session ID for this server uptime - all tool calls will use this
    server_session_id = str(uuid.uuid4())
    print(f"[OK] Server session: {server_session_id}", file=sys.stderr)

    @mcp_server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """List available tools."""
        tools = []

        # Add archetype tools
        for tool_name, schema in tool_schemas.items():
            tool_definition = archetype_data["tools"][tool_name]
            tools.append(
                types.Tool(
                    name=tool_name,
                    description=tool_definition.get("description", ""),
                    inputSchema=schema["inputSchema"],
                )
            )

        # Add search tool
        search_tool_config = config.SEARCH_TOOL
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
        """Handle tool calls."""

        nonlocal storage

        try:
            # Use the server session ID for this uptime
            session_id = server_session_id
            search_result = None
            execution_result = None

            if name == config.SEARCH_TOOL["name"]:
                # Handle search tool - implement actual search with defaults
                search_args = {
                    "query": arguments.get("query", ""),
                    "limit": arguments.get("limit", 3),
                    "search_type": arguments.get("search_type", "default"),
                    "detail": arguments.get("detail", "summary"),
                    "score_threshold": arguments.get("score_threshold", 0.4),
                    "filters": arguments.get("filters", []),
                }
                search_handler = SearchHandler(storage)
                found_memories = await search_handler.search(search_args)

                from .search.formatters import format_memories

                formatted_results = format_memories(
                    found_memories, search_args["detail"]
                )

                search_result = {"search_results": formatted_results}
            elif name in archetype_data["tools"]:
                # Handle archetype tool - separate parameters from frames
                tool_definition = archetype_data["tools"][name]

                # Extract parameters (tool-specific parameters + standard fields)
                tool_parameter_keys = set(tool_definition.get("parameters", {}).keys())
                all_parameter_keys = tool_parameter_keys | set(STANDARD_FIELDS)

                parameters = {
                    k: v for k, v in arguments.items() if k in all_parameter_keys
                }

                # Extract frames (structured output fields)
                frame_field_keys = set(tool_definition.get("frames", {}).keys())
                frames = {k: v for k, v in arguments.items() if k in frame_field_keys}

                # Validate complete AI response against tool schema
                complete_response = {**parameters, **frames}
                try:
                    tool_validators[name](complete_response)
                except Exception as e:
                    # Return validation error for AI auto-correction
                    validation_error = {
                        "error": "Tool validation failed",
                        "message": f"{str(e)}\nPlease correct the errors and retry.",
                    }
                    return [
                        types.TextContent(
                            type="text", text=json.dumps(validation_error, indent=2)
                        )
                    ]

                # Get the last memory ID and next sequence order for this session
                (
                    preceding_memory_id,
                    sequence_order,
                ) = await storage.get_last_memory_for_session(session_id)

                tool_context = {
                    "session_id": session_id,
                    "sequence_order": sequence_order,
                    "preceding_memory_id": preceding_memory_id,
                }

                memory_id = await storage.store_invocation(
                    tool_name=name,
                    parameters=parameters,
                    frames=frames,
                    archetype=archetype_data,
                    context=tool_context,
                )

                execution_result = {
                    "message": f"Tool '{name}' executed successfully",
                    "memory_id": memory_id,
                }
            else:
                raise ValueError(f"Unknown tool: {name}")

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        search_result
                        if name == config.SEARCH_TOOL["name"]
                        else execution_result,
                        indent=2,
                    ),
                )
            ]

        except Exception as e:
            error_result = {"error": str(e), "type": type(e).__name__}
            return [
                types.TextContent(type="text", text=json.dumps(error_result, indent=2))
            ]

    # Run with configured transport
    if config.transport == "stdio":

        async def run_server():
            # Initialize storage at server startup
            try:
                await storage.initialize()
                print("[OK] Storage initialized", file=sys.stderr)
                print(
                    "[READY] Fegis MCP server startup complete - ready for connections",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"[ERROR] Storage initialization failed: {e}", file=sys.stderr)
                return 1

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
