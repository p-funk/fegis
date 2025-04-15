# language: python
"""
FEGIS

FastMCP server providing language models with
structured cognitive tools and persistent cognitive artifacts.
"""

import sys
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Dict, Any, AsyncIterator, Optional

from mcp.server import Server
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from mcp_fegis_server.model_builder import ArchetypeDefinition, ArchetypeModelGenerator, ArtifactFieldMapper
from mcp_fegis_server.settings import ConfigSettings, QdrantSettings

# Load config and schema
config_settings = ConfigSettings()
archetype_definition = ArchetypeDefinition(config_settings.config_path)


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Bootstraps the server with Qdrant and ArchetypeDefinition context."""
    client = None

    try:
        # Initialize Qdrant client directly
        qdrant_config = QdrantSettings()
        client = AsyncQdrantClient(
            url=qdrant_config.qdrant_url,
            api_key=qdrant_config.qdrant_api_key,
            timeout=20
        )

        # Set the embedding model
        client.set_model(qdrant_config.fast_embed_model)

        # Ensure collection exists
        collection_exists = await client.collection_exists(qdrant_config.collection_name)

        if not collection_exists:
            # Create the collection if it doesn't exist
            await client.create_collection(
                collection_name=qdrant_config.collection_name,
                vectors_config=client.get_fastembed_vector_params()
            )
            print(f"Created new collection: {qdrant_config.collection_name}", file=sys.stderr)
        else:
            print(f"Connected to existing collection: {qdrant_config.collection_name}", file=sys.stderr)

        print("Server started successfully", file=sys.stderr)

        # Define the process_mode function that works directly with the client
        async def process_mode(ctx: Context, mode_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
            """
            Process a cognitive mode and store the result in Qdrant.

            Args:
                ctx: Request context
                mode_name: Name of the cognitive mode
                data: Data associated with the mode

            Returns:
                Dict with status information
            """
            try:
                content, metadata = ArtifactFieldMapper.to_storage_format(
                    ctx.request_context.lifespan_context["archetype_definition"],
                    mode_name,
                    data
                )

                # Store the artifact directly using the client
                await ctx.debug(f"Storing {mode_name} with metadata: {metadata}")

                # Use the client's add method directly
                await ctx.request_context.lifespan_context["client"].add(
                    collection_name=qdrant_config.collection_name,
                    documents=[content],
                    metadata=[metadata]
                )

                memory_id = metadata['provenance']['artifact_id']
                return {"stored": f"{mode_name} with artifact_id {memory_id}"}

            except Exception as e:
                await ctx.debug(f"Error in process_mode: {str(e)}")
                return {"error": f"Failed to store {mode_name}: {str(e)}"}

        yield {
            "client": client,
            "collection_name": qdrant_config.collection_name,
            "archetype_definition": archetype_definition,
            "process_mode": process_mode,
        }

    except Exception as e:
        print(f"Error in server lifespan: {e}", file=sys.stderr)
        raise
    finally:
        # Clean up resources
        if client:
            await client.close()
        print("Server shutting down", file=sys.stderr)


# Instantiate the MCP server
mcp = FastMCP("FEGIS", lifespan=server_lifespan)


def register_cognitive_tools():
    """Registers tools to implement structured cognitive modes."""
    # Get all mode names once
    mode_names = archetype_definition.get_mode_names()

    for mode in mode_names:
        # Create model only when needed (lazy)
        model = ArchetypeModelGenerator.create_model_for_mode(archetype_definition, mode)
        description = archetype_definition.get_description(mode)

        # Define the handler function with proper type annotation using the model
        async def handler(ctx: Context, input_data: model, mode_name=mode):  # Use the model here
            # Access the process_mode function from lifespan context
            return await ctx.request_context.lifespan_context["process_mode"](
                ctx, mode_name, input_data.model_dump()
            )

        # Set the name for better debugging
        handler.__name__ = f"{mode.lower()}_handler"

        # Register the tool with MCP
        mcp.tool(name=mode.lower(), description=description)(handler)
        print(f"Registered tool for mode: {mode}", file=sys.stderr)


def register_query_tools():
    """Register search and retrieval tools."""

    class SearchInput(BaseModel):
        """Input model for search operations."""
        query: str
        mode: Optional[str] = None
        facet_filter: Optional[Dict[str, str]] = None
        relata_filter: Optional[Dict[str, str]] = None
        limit: int = Field(3, description="Max results")

    # Cache the search tool description to avoid regenerating it
    @lru_cache(maxsize=1)
    def generate_search_tool_description(schema: ArchetypeDefinition) -> str:
        """Generate a description for the search tool based on the schema."""

        modes = schema.get_mode_names()

        # Collect facets efficiently
        facets = {}
        relata_fields = set()

        # Process all modes
        for mode in modes:
            mode_def = schema.get_mode_schema(mode)
            fields_dict = mode_def.get("Fields", {})

            # Process fields
            for field_name, field_schema in fields_dict.items():
                # Check for facets
                facet_name = field_schema.get("Facet")
                if facet_name and facet_name not in facets:
                    facets[facet_name] = schema.get_facet_schema(facet_name)

                # Check for relata fields
                if field_schema.get("Type") == "List[str]":
                    relata_fields.add(field_name)

        # Build comma-separated strings for each dynamic element
        modes_str = ", ".join(modes) if modes else "None"
        facets_str = ", ".join(facets.keys()) if facets else "None"
        relata_str = ", ".join(relata_fields) if relata_fields else "None"

        # Generate the description string with the dynamic values
        return f"""
        Search memory entries by content, structure, or relationships.

        This tool enables cognitive artifact retrieval through multiple dimensions:
          • **Modes**: Filter by specific cognitive tool types (available: {modes_str})
          • **Facets**: Filter by qualitative metadata properties (available: {facets_str})
          • **Relata**: Locate connected artifacts through relationship fields (available: {relata_str})
          • **Content**: Search by semantic similarity to your query text

        Effective searching often starts with content queries for broad exploration,
        then applies filters to refine results. Try using distinctive phrases for better
        precision.

        The 'limit' parameter controls how many results are returned. Construct queries
        thoughtfully—this tool works best when you clearly identify what you're seeking
        and make use of the relevant parameters.
        """

    @mcp.tool(
        name="fegis_search",
        description=generate_search_tool_description(archetype_definition)
    )
    async def fegis_search(ctx: Context, input_data: SearchInput):
        """Search for artifacts based on content and metadata filters."""
        schema = ctx.request_context.lifespan_context["archetype_definition"]
        client = ctx.request_context.lifespan_context["client"]
        collection_name = ctx.request_context.lifespan_context["collection_name"]

        # Build query filter conditions
        conditions = []

        # Check mode validity early
        if input_data.mode:
            if input_data.mode not in schema.get_mode_names():
                return {"error": f"Unknown mode: {input_data.mode}"}
            conditions.append(FieldCondition(key="mode", match=MatchValue(value=input_data.mode)))

        # Add facet filters
        if input_data.facet_filter:
            for name, value in input_data.facet_filter.items():
                conditions.append(FieldCondition(key=f"facets.{name}", match=MatchValue(value=value)))

        # Add relata filters
        if input_data.relata_filter:
            for name, value in input_data.relata_filter.items():
                conditions.append(FieldCondition(key=f"relata.{name}", match=MatchValue(value=value)))

        # Create filter only if conditions exist
        query_filter = Filter(must=conditions) if conditions else None

        # Use the client directly
        results = await client.query(
            collection_name=collection_name,
            query_text=input_data.query,
            query_filter=query_filter,
            limit=input_data.limit
        )

        # Format results consistently
        return {
            "results": [
                {"content": r.document, "score": r.score, "metadata": r.metadata}
                for r in results
            ]
        }

    class RetrieveInput(BaseModel):
        """Input model for artifact retrieval by memory ID."""
        artifact_id: str

    @mcp.tool(
        name="fegis_retrieve",
        description="Retrieve a specific cognitive artifact by its memory ID"
    )
    async def fegis_retrieve(ctx: Context, input_data: RetrieveInput):
        """Retrieve a single artifact by its memory ID."""
        client = ctx.request_context.lifespan_context["client"]
        collection_name = ctx.request_context.lifespan_context["collection_name"]

        # Create a filter for exact ID match
        filter_obj = Filter(
            must=[FieldCondition(
                key="provenance.artifact_id",
                match=MatchValue(value=input_data.artifact_id)
            )]
        )

        # Use the client directly
        results = await client.query(
            collection_name=collection_name,
            query_text="",
            query_filter=filter_obj,
            limit=1
        )

        if not results:
            return {"error": f"No cognitive artifact found with memory ID: {input_data.artifact_id}"}

        result = results[0]
        return {
            "artifact": {
                "content": result.document,
                "metadata": result.metadata
            }
        }


def clear_caches():
    """Clear all function caches to ensure fresh tool registrations."""
    # Get all functions in this module
    for name, obj in globals().items():
        # Check if the object has a cache_clear method (indicating it's cached with lru_cache)
        if hasattr(obj, 'cache_clear'):
            print(f"Clearing cache for {name}", file=sys.stderr)
            obj.cache_clear()

def register_all_tools():
    """Register all cognitive and query tools."""
    # Clear any cached values first
    clear_caches()
    
    print("Registering FEGIS tools...", file=sys.stderr)
    
    # Track registered tools for debugging
    registered_tools = []
    
    # Monkey patch the tool decorator to track registrations
    original_tool_decorator = mcp.tool
    def tracking_tool_decorator(*args, **kwargs):
        name = kwargs.get('name', args[0] if args else None)
        if name:
            registered_tools.append(name)
        return original_tool_decorator(*args, **kwargs)
    
    # Replace the decorator temporarily
    mcp.tool = tracking_tool_decorator
    
    try:
        register_cognitive_tools()
        register_query_tools()
    finally:
        # Restore the original decorator
        mcp.tool = original_tool_decorator
    
    # Log all registered tools for debugging
    print("All FEGIS tools registered:", file=sys.stderr)
    for tool_name in registered_tools:
        print(f"  - {tool_name}", file=sys.stderr)


# Register tools when the module is imported
register_all_tools()
