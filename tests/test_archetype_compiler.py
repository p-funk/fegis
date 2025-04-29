import pytest
import os
from datetime import datetime

from fegis.archetype_compiler import (
    ArchetypeDefinition,
    ArchetypeModelGenerator,
    ArtifactFieldMapper,
)

# Fix the path to correctly locate the test file
# Assuming the test is in PROJECT_ROOT/tests and the archetype is in PROJECT_ROOT/archetypes
# Get the absolute path to the current file
current_dir = os.path.dirname(os.path.abspath(__file__))
# Navigate to the project root and then to the archetypes directory
ARCHETYPE = os.path.join(os.path.dirname(current_dir), "archetypes", "test_fegis.yaml")


@pytest.fixture(scope="module")
def schema():
    # load the test file
    return ArchetypeDefinition(ARCHETYPE)


def test_parse_archetype(schema):
    # sanity‐check top‐level fields
    arc = schema.archetype
    assert arc.version, "version must be set"
    assert arc.title, "title must be set"
    assert arc.processes, "there should be at least one process"


def test_all_tools_generate_models(schema):
    # make sure every tool can produce a Pydantic model
    for tool_name in schema.tools():
        Model = ArchetypeModelGenerator.create(schema, tool_name)
        # In Pydantic v2, we need to check model_fields instead of hasattr on the class
        title_field = schema.use_title_field(tool_name)
        content_field = schema.content_field(tool_name)

        assert title_field in Model.model_fields, f"Title field '{title_field}' not found in model for tool '{tool_name}'"
        assert content_field in Model.model_fields, f"Content field '{content_field}' not found in model for tool '{tool_name}'"


def test_roundtrip_storage(schema):
    # pick one tool (or parametrize over all) to roundtrip through validation + storage
    for tool_name in schema.tools():
        Model = ArchetypeModelGenerator.create(schema, tool_name)

        # build minimal valid kwargs: title + content + any required processes/frames
        kwargs = {
            schema.use_title_field(tool_name): "TT",
            schema.content_field(tool_name): "CC",
        }

        # auto‐populate any required process fields with their defaults (or sample values)
        tool = schema.tool(tool_name)

        # Add tool-specific required fields based on YAML definition
        if tool_name == "TestResult":
            kwargs["test_reference"] = "test-ref-123"
        elif tool_name == "TestFixture":
            kwargs["setup"] = "setup code"
            kwargs["teardown"] = "teardown code"
            kwargs["dependencies"] = []
        elif tool_name == "TestAssertion":
            kwargs["expected"] = "expected value"
            kwargs["actual"] = "actual value"
            kwargs["assertion_type"] = "equality"
            kwargs["related_tests"] = []
        elif tool_name == "TestCase":
            kwargs["dependencies"] = []
        elif tool_name == "TestSuite":
            kwargs["test_cases"] = []

        # Add process fields if they're required
        if tool.processes:
            for fname, fld in tool.processes.items():
                # Check for both Pydantic v1 and v2 attribute names
                is_required = hasattr(fld, 'is_required') and fld.is_required or hasattr(fld,
                                                                                         'required') and fld.required
                if is_required and fname not in kwargs:
                    kwargs[fname] = fld.default or "sample"

        # Add frames fields if they're required
        if tool.frames:
            for rname, rfld in tool.frames.items():
                if rfld is None:
                    continue

                # Check for both Pydantic v1 and v2 attribute names
                is_required = hasattr(rfld, 'is_required') and rfld.is_required or hasattr(rfld,
                                                                                           'required') and rfld.required

                if is_required and rname not in kwargs:
                    # use empty list for List, False for bool, 0.0 for float
                    if rfld.type == "List":
                        kwargs[rname] = []
                    elif rfld.type == "bool":
                        kwargs[rname] = False
                    elif rfld.type == "float":
                        kwargs[rname] = 0.0
                    else:
                        kwargs[rname] = "sample-data"

        # Instantiate the model with our prepared data
        inst = Model(**kwargs)
        data = inst.model_dump()

        # Add artifact_uuid to data if needed by ArtifactFieldMapper
        if "artifact_uuid" not in data:
            data["artifact_uuid"] = "test-uuid-12345"

        content, meta = ArtifactFieldMapper.to_storage(schema, tool_name, data)

        # validate storage output
        assert content == kwargs[schema.content_field(tool_name)]
        assert meta["tool"] == tool_name
        assert meta["title"] == kwargs[schema.use_title_field(tool_name)]

        # Check for artifact_uuid if it should be in meta
        if "artifact_uuid" in meta:
            assert isinstance(meta["artifact_uuid"], str) and meta["artifact_uuid"]

        # Verify created_at if it exists in meta
        if "created_at" in meta:
            # Handle both string and datetime formats
            if isinstance(meta["created_at"], str):
                # Attempt to parse the datetime string
                try:
                    datetime.strptime(meta["created_at"], "%B %d, %Y at %I:%M %p")
                except ValueError:
                    pytest.fail(f"Invalid created_at format: {meta['created_at']}")