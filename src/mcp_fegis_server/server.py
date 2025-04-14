# language: python
"""
FEGIS

FastMCP server providing language models with
structured cognitive tools and persistent cognitive artifacts.
"""

import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, AsyncIterator, Type, Optional

from mcp.server import Server
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from mcp_fegis_server.model_builder import ArchetypeDefinition, ArchetypeModelGenerator, ArtifactFieldMapper
from mcp_fegis_server.qdrant import QdrantConnector
from mcp_fegis_server.settings import ConfigSettings, QdrantSettings

# Load config and schema
config_settings = ConfigSettings()
archetype_definition = ArchetypeDefinition(config_settings.config_path)

# Instantiate the MCP server
mcp = FastMCP("FEGIS")

@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Bootstraps the server with Qdrant and ArchetypeDefinition context."""
    try:
        qdrant_config = QdrantSettings()
        qdrant_connector = QdrantConnector(
            qdrant_url=qdrant_config.qdrant_url,
            qdrant_api_key=qdrant_config.qdrant_api_key,
            collection_name=qdrant_config.collection_name,
            fastembed_model=qdrant_config.fast_embed_model,
        )
        await qdrant_connector.ensure_collection_exists()

        async def process_mode(ctx: Context, mode_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
            content, metadata = ArtifactFieldMapper.to_storage_format(
                ctx.request_context.lifespan_context["archetype_definition"],
                mode_name,
                data
            )
            await ctx.debug(f"Storing {mode_name} with metadata: {metadata}")
            await ctx.request_context.lifespan_context["qdrant_connector"].client.add(
                collection_name=qdrant_connector._collection_name,
                documents=[content],
                metadata=[metadata],
            )
            return {"stored": f"{mode_name} with memory_id {metadata['provenance']['memory_id']}"}

        yield {
            "qdrant_connector": qdrant_connector,
            "archetype_definition": archetype_definition,
            "process_mode": process_mode,
        }

    except Exception as e:
        print(f"Error in server lifespan: {e}", file=sys.stderr)
        raise
    finally:
        print("Server shutting down", file=sys.stderr)


def register_cognitive_tools():
    def create_tool_handler(mode_name: str, model_type: Type[BaseModel]):
        async def handler(ctx: Context, input_data: model_type):
            return await ctx.request_context.lifespan_context["process_mode"](
                ctx, mode_name, input_data.model_dump()
            )
        handler.__name__ = f"{mode_name.lower()}_handler"
        return handler

    for mode in archetype_definition.get_mode_names():
        model = ArchetypeModelGenerator.create_model_for_mode(archetype_definition, mode)
        description = archetype_definition.get_description(mode)
        mcp.tool(name=mode.lower(), description=description)(
            create_tool_handler(mode, model)
        )
        print(f"Registered tool for mode: {mode}", file=sys.stderr)


def register_query_tools():
    class SearchInput(BaseModel):
        query: str
        mode: Optional[str] = None
        facet_filter: Optional[Dict[str, str]] = None
        relata_filter: Optional[Dict[str, str]] = None
        limit: int = Field(5, description="Max results")

    @mcp.tool(
        name="search_artifacts",
        description="Search cognitive artifacts by content, structure, or relationships."
    )
    async def search_artifacts(ctx: Context, input_data: SearchInput):
        schema = ctx.request_context.lifespan_context["archetype_definition"]
        qdrant = ctx.request_context.lifespan_context["qdrant_connector"]

        conditions = []

        if input_data.mode:
            if input_data.mode not in schema.get_mode_names():
                return {"error": f"Unknown mode: {input_data.mode}"}
            conditions.append(FieldCondition(key="mode", match=MatchValue(value=input_data.mode)))

        if input_data.facet_filter:
            for name, value in input_data.facet_filter.items():
                conditions.append(FieldCondition(key=f"facets.{name}", match=MatchValue(value=value)))

        if input_data.relata_filter:
            for name, value in input_data.relata_filter.items():
                conditions.append(FieldCondition(key=f"relata.{name}", match=MatchValue(value=value)))

        query_filter = Filter(must=conditions) if conditions else None

        results = await qdrant.client.query(
            collection_name=qdrant._collection_name,
            query_text=input_data.query,
            query_filter=query_filter,
            limit=input_data.limit
        )

        return {
            "results": [
                {"content": r.document, "score": r.score, "metadata": r.metadata}
                for r in results
            ]
        }

    class RetrieveInput(BaseModel):
        memory_id: str

    @mcp.tool(
        name="retrieve_artifact",
        description="Retrieve a specific cognitive artifact by its memory ID"
    )
    async def retrieve_artifact(ctx: Context, input_data: RetrieveInput):
        qdrant_connector = ctx.request_context.lifespan_context["qdrant_connector"]
        filter_obj = Filter(
            must=[FieldCondition(
                key="provenance.memory_id",
                match=MatchValue(value=input_data.memory_id)
            )]
        )

        results = await qdrant_connector.client.query(
            collection_name=qdrant_connector._collection_name,
            query_text="",
            query_filter=filter_obj,
            limit=1
        )

        if not results:
            return {"error": f"No cognitive artifact found with memory ID: {input_data.memory_id}"}

        result = results[0]
        return {
            "artifact": {
                "content": result.document,
                "metadata": result.metadata
            }
        }


def register_all_tools():
    register_cognitive_tools()
    register_query_tools()
    print("All FEGIS tools registered", file=sys.stderr)

# Attach lifespan and register tools
mcp.lifespan = server_lifespan
register_all_tools()
