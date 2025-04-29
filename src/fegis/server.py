"""
FastMCP server that wires Archetype-defined tools straight into Qdrant.
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
    ArtifactFieldMapper,
)
from .constants import TOOL_NAME
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

    async def process_tool(ctx: Context, mode: str, data: Dict[str, Any]) -> Dict[str, Any]:
        content, meta = ArtifactFieldMapper.to_storage(schema, mode, data)
        await ctx.debug(f"Storing {mode} with metadata: {meta}")

        # Always use auto-generated point IDs
        ids = await qdrant.client.add(
            collection_name=qdrant.col,
            documents=[content],
            metadata=[meta],
        )
        point_id = ids[0]
        return {"stored": mode, "artifact_uuid": point_id}

    print("Server started successfully", file=sys.stderr)
    yield {
        "schema": schema,
        "qdrant": qdrant,
        "process_tool": process_tool,
    }

    print("Server shutting down", file=sys.stderr)
    await qdrant.client.close()


mcp = FastMCP("FEGIS", lifespan=lifespan)


# ---------- tool registration ---------- #
print("Registering FEGIS tools...", file=sys.stderr)
registered_tools = []

def _make_handler(mode: str, model_cls):
    async def handler(ctx: Context, input_data: model_cls):
        return await ctx.request_context.lifespan_context["process_tool"](
            ctx, mode, input_data.model_dump()
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
    return f"Create a new {tool_name} artifact."


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
    query: str
    tool: Optional[str] = None
    process_filter: Optional[Dict[str, str]] = None
    frame_filter: Optional[Dict[str, str]] = None
    limit: int = Field(3, ge=1, le=5)
    ef: Optional[int] = Field(None, ge=16, le=512,
                              description="Override HNSW ef parameter for this query")


@lru_cache(maxsize=1)
def search_tool_description() -> str:
    try:
        # Generate the description string with the dynamic values
        tools_list = list(schema.tools())
        processes_list = list(schema.processes().keys()) if callable(getattr(schema, "processes", None)) else []

        return (
            "Search stored memories by freeform content, text similarity.\n\n"
            f"• **Tool names:** {', '.join(tools_list) or 'none'}\n"
            f"• **Processes:** {', '.join(processes_list) or 'none'}\n"
            f"• **Query:** Freeform text or structured query.\n"
            f"• **Created Time** %B %d, %Y at %I:%M %p for time related queries.\n"
            "Use 'limit' to control result count."
        )
    except Exception as e:
        print(f"Error generating search tool description: {e}", file=sys.stderr)
        return "Search stored memories by text similarity, processes or relationships."


@mcp.tool(name="search_memories", description=search_tool_description())
async def search_memories(ctx: Context, inp: SearchInput):
    qdrant = ctx.request_context.lifespan_context["qdrant"]
    conditions = []

    if inp.tool:
        # Updated to use schema.tools() method
        if inp.tool not in schema.tools():
            return {"error": f"Unknown tool: {inp.tool}"}
        conditions.append(FieldCondition(key=TOOL_NAME, match=MatchValue(value=inp.tool)))

    for k, v in (inp.process_filter or {}).items():
        conditions.append(FieldCondition(key=f"processes.{k}", match=MatchValue(value=v)))
    for k, v in (inp.frame_filter or {}).items():
        conditions.append(FieldCondition(key=f"frames.{k}", match=MatchValue(value=v)))

    try:
        # Optimize: Use scroll instead of query for empty queries
        if not inp.query:
            res = await qdrant.client.scroll(
                collection_name=qdrant.col,
                scroll_filter=Filter(must=conditions) if conditions else None,
                with_vectors=False,
                limit=inp.limit,
            )
            return {"results": [{"content": p.payload, "score": 1.0, "meta": p.payload} for p in res.points]}
        else:
            # Use vector search for non-empty queries
            res = await qdrant.client.query(
                collection_name=qdrant.col,
                query_text=inp.query,
                query_filter=Filter(must=conditions) if conditions else None,
                search_params={"ef": inp.ef} if inp.ef else None,
                with_vectors=False,
                limit=inp.limit,
            )
            return {"results": [{"content": r.document, "score": r.score, "meta": r.metadata} for r in res]}
    except Exception as e:
        print(f"Search error: {e}", file=sys.stderr)
        return {"error": f"Search failed: {str(e)}"}

registered_tools.append("search_memories")
print("Registered tool for search", file=sys.stderr)


class RetrieveInput(BaseModel):
    artifact_uuid: str


@mcp.tool(name="retrieve_memory", description="Retrieve a memory by its artifact_uuid.")
async def retrieve_memory(ctx: Context, inp: RetrieveInput):
    qdrant = ctx.request_context.lifespan_context["qdrant"]
    try:
        # Use direct point ID retrieval - much faster than vector query
        res = await qdrant.client.retrieve(
            collection_name=qdrant.col,
            ids=[inp.artifact_uuid],
            with_vectors=False
        )
        if not res:
            return {"error": "Not found"}
        r = res[0]
        return {"artifact": {"content": r.payload, "meta": r.payload}}
    except Exception as e:
        print(f"Retrieve error: {e}", file=sys.stderr)
        return {"error": f"Retrieval failed: {str(e)}"}

registered_tools.append("retrieve_memory")
print("Registered tool for retrieve", file=sys.stderr)

# Print summary of all registered tools
print("All FEGIS tools registered:", file=sys.stderr)
for tool_name in registered_tools:
    print(f"  - {tool_name}", file=sys.stderr)
