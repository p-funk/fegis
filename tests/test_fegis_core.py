import pytest
import uuid
import os
from pathlib import Path
from fegis.archetype_compiler import ArchetypeDefinition, ArchetypeModelGenerator, TraceFieldMapper
from fegis.server import schema, registered_tools
# No constants needed for this test file

# --- ARCHETYPE DEFINITION ---
@pytest.mark.parametrize("yaml_file", list(Path("archetypes").rglob("*.yml")) + list(Path("archetypes").rglob("*.yaml")))
def test_all_archetypes_compile(yaml_file):
    """
    Ensure every YAML archetype file compiles via ArchetypeDefinition.
    """
    # Should not raise
    ArchetypeDefinition(yaml_file)

# --- MODEL + TRACE ---
@pytest.mark.parametrize("tool", schema.tools())
def test_tool_model_and_trace(tool):
    """
    Each registered tool should generate a valid Pydantic model and trace data.
    """
    Model = ArchetypeModelGenerator.create(schema, tool)
    title_field = schema.title_field(tool)
    content_field = schema.content_field(tool)

    # Generate minimal valid input
    data = {title_field: "test title", content_field: "test content"}
    tool_model = schema.tool(tool)
    # Populate parameters
    for fname, f in (tool_model.parameters or {}).items():
        data[fname] = f.default or "test"
    # Populate required frames
    for fname, f in (tool_model.frames or {}).items():
        if f and f.required:
            data[fname] = [] if f.type == "List" else 0.0 if f.type == "number" else False if f.type == "bool" else "x"

    inst = Model(**data)
    content, meta = TraceFieldMapper.to_storage(schema, tool, inst.model_dump())
    assert isinstance(content, str)
    assert meta.get("tool") == tool

# --- SERVER REGISTRATION ---

def test_registered_tools_match_schema():
    """All archetype-defined tools must be registered."""
    defined = {tool.lower() for tool in schema.tools()}
    assert defined.issubset(set(registered_tools))


def test_builtin_tools_are_registered():
    """Built-in tools search_archive and retrieve_trace should be present."""
    assert "search_archive" in registered_tools
    assert "retrieve_trace" in registered_tools

# --- HANDLER LIFECYCLE ---
from types import SimpleNamespace

@pytest.mark.asyncio
async def test_handler_invokes_generate_tool_trace():
    """
    Ensure that the MCP handler created by _make_handler correctly calls generate_tool_trace
    """
    # Choose any defined tool
    tool = schema.tools()[0]
    Model = ArchetypeModelGenerator.create(schema, tool)
    tool_model = schema.tool(tool)

    # Fake generate_tool_trace that echoes inputs
    async def fake_generate_tool_trace(ctx, mode, data):
        return {"stored": mode, "trace_uuid": "fake-uuid", "echo": data}

    # Build a fake context with our fake lifespan
    fake_ctx = SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context={"generate_tool_trace": fake_generate_tool_trace}
        )
    )

    # Create handler directly
    from fegis.server import _make_handler
    handler = _make_handler(tool, Model)

    # Instantiate minimal valid model input for the handler
    title_field = schema.title_field(tool)
    content_field = schema.content_field(tool)
    init_data = {title_field: "T", content_field: "C"}
    # Populate parameter defaults if any
    for fname, f in (tool_model.parameters or {}).items():
        init_data[fname] = f.default or "test"
    # Populate required frames
    for fname, f in (tool_model.frames or {}).items():
        if f and f.required:
            init_data[fname] = [] if f.type == "List" else 0.0 if f.type == "number" else False if f.type == "bool" else "x"

    inst = Model(**init_data)

    # Call the handler
    result = await handler(fake_ctx, inst)

    # Verify it forwarded correctly
    assert result["stored"] == tool
    assert result["trace_uuid"] == "fake-uuid"
    assert result["echo"] == inst.model_dump()