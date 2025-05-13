"""
Fegis MCP Server Implementation

Implements a Model Control Protocol (MCP) server that dynamically registers tools
based on YAML archetype definitions. The server architecture comprises:

1. Archetype Compilation: Loading and validating YAML specifications into runtime models
2. Tool Registration: Dynamically generating MCP-compatible handlers for each tool
3. Vector Persistence: Automatic storage of tool invocations in Qdrant
4. Memory Retrieval: Search and direct access to the Trace Archive

Every tool invocation follows a consistent lifecycle:
1. Validate input against the compiled archetype model
2. Process the invocation through the tool-specific handler
3. Transform the result into a standardized trace structure
4. Persist the trace in Qdrant with semantic content and structured metadata
5. Return a confirmation with the generated trace_uuid for reference

This architecture creates a semantic memory system that maintains a persistent,
searchable record of all interactions while enforcing consistent structure.
"""

import sys
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, AsyncIterator, Dict, Optional

from mcp.server import Server
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from .archetype_compiler import (
    ArchetypeDefinition,
    ArchetypeModelGenerator,
    TraceFieldMapper,
)
from .constants import DEFAULTS, FORMAT, ERROR
from .qdrant_connector import QdrantConnector
from .settings import ConfigSettings, QdrantSettings

# No structured logging - use simple print statements to stderr

cfg = ConfigSettings()

# Wrap the schema loading in a try-except to provide better error messages
try:
    schema = ArchetypeDefinition(cfg.config_path)
    print(f"Schema loaded from {cfg.config_path}", file=sys.stderr)
except Exception as e:
    print(f"Error loading schema from {cfg.config_path}: {e}", file=sys.stderr)
    raise


@asynccontextmanager
async def lifespan(_: Server) -> AsyncIterator[dict]:
    print("Server startup initiated...", file=sys.stderr)
    qdrant_cfg = QdrantSettings()
    qdrant = QdrantConnector(qdrant_cfg, schema)
    await qdrant.ensure_ready()
    print(f"Connected to Qdrant collection: {qdrant.col}", file=sys.stderr)

    async def generate_tool_trace(ctx: Context, mode: str, data: Dict[str, Any]) -> Dict[str, Any]:
        content, meta = TraceFieldMapper.to_storage(schema, mode, data)
        await ctx.debug(f"Storing {mode} with metadata: {meta}")

        # Always use auto-generated point IDs
        ids = await qdrant.client.add(
            collection_name=qdrant.col,
            documents=[content],
            metadata=[meta],
        )
        point_id = ids[0]
        return {"stored": mode, "trace_uuid": point_id}

    print("Server started successfully", file=sys.stderr)
    yield {
        "schema": schema,
        "qdrant": qdrant,
        "generate_tool_trace": generate_tool_trace,
    }

    print("Server shutting down", file=sys.stderr)
    await qdrant.client.close()


mcp = FastMCP("Fegis", lifespan=lifespan)

# ---------- tool registration ---------- #
print("Registering Fegis tools...", file=sys.stderr)
registered_tools = []


def _make_handler(mode: str, model_cls):
    async def handler(ctx: Context, trace_data: model_cls):
        return await ctx.request_context.lifespan_context["generate_tool_trace"](
            ctx, mode, trace_data.model_dump()
        )

    handler.__name__ = f"{mode.lower()}_handler"
    return handler


# Add a description method to ArchetypeDefinition if it doesn't exist
def get_tool_description(schema, tool_name):
    """Get description for a tool, falling back to a default if not present."""
    mode = schema.tool(tool_name)
    # Check if the tool has a description attribute, otherwise use a default
    if hasattr(mode, "description") and mode.description:
        return mode.description
    return f"Create a new {tool_name} trace."


# Updated to use schema.tools() method and handle missing descriptions
for tool in schema.tools():
    try:
        mdl = ArchetypeModelGenerator.create(schema, tool)
        description = get_tool_description(schema, tool)

        mcp.tool(name=tool.lower(), description=description)(
            _make_handler(tool, mdl)
        )
        registered_tools.append(tool.lower())
        print(f"Registered tool for tool: {tool}", file=sys.stderr)
    except Exception as e:
        print(f"Error registering tool for tool {tool}: {e}", file=sys.stderr)


class SearchInput(BaseModel):
    """Input schema for performing trace archive searches by content, tool type, parameter values, or frame data."""
    query: str = Field()
    tool: Optional[str] = Field(None)
    parameter_filter: Optional[Dict[str, Any]] = Field(None)
    frame_filter: Optional[Dict[str, Any]] = Field(None)
    limit: int = Field(DEFAULTS["limit"], ge=DEFAULTS["min_limit"], le=DEFAULTS["max_limit"])
    ef: Optional[int] = Field(None, ge=DEFAULTS["min_ef"], le=DEFAULTS["max_ef"])


def search_tool_description() -> str:
    return "Search stored memories by content similarity, tool type, parameter values, or frame data. Follow relationships between traces to explore connected thoughts and historical progression."


@mcp.tool(name="search_archive",
          description="Search stored memories by content similarity, tool type, parameter values, or frame data. Follow relationships between traces to explore connected thoughts and historical progression.")
async def search_archive(ctx: Context, archive_query: SearchInput):
    """An elegant approach that leverages Qdrant's internal type conversion."""
    qdrant = ctx.request_context.lifespan_context["qdrant"]

    # Build filter conditions directly without manual type conversion
    conditions = []

    # Tool filtering
    if archive_query.tool:
        conditions.append(FieldCondition(key="tool", match=MatchValue(value=archive_query.tool)))

    # Parameter filtering - let Qdrant handle conversion internally
    if archive_query.parameter_filter:
        for k, v in archive_query.parameter_filter.items():
            conditions.append(FieldCondition(key=f"parameters.{k}", match=MatchValue(value=v)))

    # Frame filtering - let Qdrant handle conversion internally
    if archive_query.frame_filter:
        for k, v in archive_query.frame_filter.items():
            conditions.append(FieldCondition(key=f"frames.{k}", match=MatchValue(value=v)))

    try:
        # Optimize: Use scroll instead of query for empty queries
        if not archive_query.query:
            # Directly unpack the tuple returned by scroll
            points, _ = await qdrant.client.scroll(
                collection_name=qdrant.col,
                scroll_filter=Filter(must=conditions) if conditions else None,
                with_vectors=False,
                limit=archive_query.limit,
            )
            return {
                "results": [{"id": p.id, "content": p.payload, "score": 1.0, "meta": p.payload} for p in points]
            }
        else:
            # Use vector search for non-empty queries
            res = await qdrant.client.query(
                collection_name=qdrant.col,
                query_text=archive_query.query,
                query_filter=Filter(must=conditions) if conditions else None,
                search_params={"ef": archive_query.ef} if archive_query.ef else None,
                with_vectors=False,
                limit=archive_query.limit,
            )
            return {"results": [{"id": r.id, "content": r.document, "score": r.score, "meta": r.metadata} for r in res]}
    except Exception as e:
        print(f"Search error: {e}", file=sys.stderr)
        return {"error": ERROR["search_failed"].format(str(e))}

registered_tools.append("search_archive")
print("Registered tool for search", file=sys.stderr)


class RetrieveInput(BaseModel):
    trace_uuid: str = Field(description="The trace_uuid of the trace to retrieve")


@mcp.tool(name="retrieve_trace", description="Retrieve a memory by its trace_uuid.")
async def retrieve_trace(ctx: Context, trace_input: RetrieveInput):
    qdrant = ctx.request_context.lifespan_context["qdrant"]
    try:
        # Use direct point ID retrieval - much faster than vector query
        res = await qdrant.client.retrieve(
            collection_name=qdrant.col,
            ids=[trace_input.trace_uuid],
            with_vectors=False
        )
        if not res:
            return {"error": ERROR["not_found"]}
        r = res[0]
        return {"trace": {"content": r.payload, "meta": r.payload}}
    except Exception as e:
        print(f"Retrieve error: {e}", file=sys.stderr)
        return {"error": f"Retrieval failed: {str(e)}"}


registered_tools.append("retrieve_trace")
print("Registered tool for retrieve", file=sys.stderr)

# Print summary of all registered tools
print("All Fegis tools registered:", file=sys.stderr)
for tool_name in registered_tools:
    print(f"  - {tool_name}", file=sys.stderr)