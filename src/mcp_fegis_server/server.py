"""
FastMCP server that wires Archetype‑defined tools straight into Qdrant.
"""
import sys
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, AsyncIterator, Dict, Optional

from mcp.server import Server
from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

from .constants import MODE_FIELD, ARTIFACT_ID_FIELD
from .model_builder import (
    ArchetypeDefinition,
    ArchetypeModelGenerator,
    ArtifactFieldMapper,
)
from .qdrant_connector import QdrantConnector
from .settings import ConfigSettings, QdrantSettings

cfg = ConfigSettings()
schema = ArchetypeDefinition(cfg.config_path)


@asynccontextmanager
async def lifespan(_: Server) -> AsyncIterator[dict]:
    print("Server startup initiated...", file=sys.stderr)
    qdrant_cfg = QdrantSettings()
    qdrant = QdrantConnector(qdrant_cfg)
    await qdrant.ensure_ready()
    print(f"Connected to Qdrant collection: {qdrant.col}", file=sys.stderr)

    async def process_mode(ctx: Context, mode: str, data: Dict[str, Any]) -> Dict[str, Any]:
        content, meta = ArtifactFieldMapper.to_storage(schema, mode, data)
        await ctx.debug(f"Storing {mode} with metadata: {meta}")

        await qdrant.client.add(
            collection_name=qdrant.col,
            documents=[content],
            metadata=[meta],
        )
        return {"stored": meta["provenance"]["artifact_id"]}

    print("Server started successfully", file=sys.stderr)
    yield {
        "schema": schema,
        "qdrant": qdrant,
        "process_mode": process_mode,
    }

    print("Server shutting down", file=sys.stderr)
    await qdrant.client.close()



mcp = FastMCP("FEGIS", lifespan=lifespan)


# ---------- tool registration ---------- #
print("Registering FEGIS tools...", file=sys.stderr)
registered_tools = []

def _make_handler(mode: str, model_cls):
    async def handler(ctx: Context, input_data: model_cls):
        return await ctx.request_context.lifespan_context["process_mode"](
            ctx, mode, input_data.model_dump()
        )

    handler.__name__ = f"{mode.lower()}_handler"
    return handler


for mode in schema.modes:
    mdl = ArchetypeModelGenerator.create(schema, mode)
    mcp.tool(name=mode.lower(), description=schema.description(mode))(
        _make_handler(mode, mdl)
    )
    registered_tools.append(mode.lower())
    print(f"Registered tool for mode: {mode}", file=sys.stderr)



class SearchInput(BaseModel):
    query: str
    mode: Optional[str] = None
    facet_filter: Optional[Dict[str, str]] = None
    relata_filter: Optional[Dict[str, str]] = None
    limit: int = Field(3, ge=1, le=20)
    ef: Optional[int] = Field(None, ge=16, le=512,
                              description="Override HNSW ef parameter for this query")


@lru_cache
def search_tool_description() -> str:
    # Generate the description string with the dynamic values
    return (
        "Search cognitive artifacts by text similarity, facets or relationships.\n\n"
        f"• **Modes:** {', '.join(schema.modes) or 'none'}\n"
        f"• **Facets:** {', '.join(schema.facets) or 'none'}\n"
        f"• **Relata fields:** {', '.join(schema.relata_fields) or 'none'}\n"
        "Use 'limit' to control result count."
    )


@mcp.tool(name="fegis_search", description=search_tool_description())
async def fegis_search(ctx: Context, inp: SearchInput):
    qdrant = ctx.request_context.lifespan_context["qdrant"]
    conditions = []

    if inp.mode:
        if inp.mode not in schema.modes:
            return {"error": f"Unknown mode: {inp.mode}"}
        conditions.append(FieldCondition(key=MODE_FIELD, match=MatchValue(value=inp.mode)))

    for k, v in (inp.facet_filter or {}).items():
        conditions.append(FieldCondition(key=f"facets.{k}", match=MatchValue(value=v)))
    for k, v in (inp.relata_filter or {}).items():
        conditions.append(FieldCondition(key=f"relata.{k}", match=MatchValue(value=v)))

    res = await qdrant.client.query(
        collection_name=qdrant.col,
        query_text=inp.query,
        query_filter=Filter(must=conditions) if conditions else None,
        search_params={"ef": inp.ef} if inp.ef else None,
        with_vectors=False,
        limit=inp.limit,
    )
    return {"results": [{"content": r.document, "score": r.score, "meta": r.metadata} for r in res]}

registered_tools.append("fegis_search")
print("Registered tool for search", file=sys.stderr)


class RetrieveInput(BaseModel):
    artifact_id: str


@mcp.tool(name="fegis_retrieve", description="Retrieve a cognitive artifact by its artifact_id.")
async def fegis_retrieve(ctx: Context, inp: RetrieveInput):
    qdrant = ctx.request_context.lifespan_context["qdrant"]
    res = await qdrant.client.query(
        collection_name=qdrant.col,
        query_text="",
        query_filter=Filter(
            must=[FieldCondition(key=ARTIFACT_ID_FIELD, match=MatchValue(value=inp.artifact_id))]
        ),
        limit=1,
    )
    if not res:
        return {"error": "Not found"}
    r = res[0]
    return {"artifact": {"content": r.document, "meta": r.metadata}}

registered_tools.append("fegis_retrieve")
print("Registered tool for retrieve", file=sys.stderr)

# Print summary of all registered tools
print("All FEGIS tools registered:", file=sys.stderr)
for tool_name in registered_tools:
    print(f"  - {tool_name}", file=sys.stderr)