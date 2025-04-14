"""
Basic tests for FEGIS server components.

These tests verify the core functionality of the FEGIS server without extensive mocking.
"""

import uuid
import pytest
from pathlib import Path

from mcp_fegis_server.model_builder import ArchetypeDefinition, ArchetypeModelGenerator, ArtifactFieldMapper
from qdrant_client import AsyncQdrantClient


def test_archetype_definition():
    """Test that ArchetypeDefinition loads and parses YAML correctly."""
    definition = ArchetypeDefinition("../archetypes/test_fegis.yaml")
    
    # Verify mode names
    modes = definition.get_mode_names()
    assert "TestCase" in modes
    assert "TestSuite" in modes
    
    # Verify content field detection
    content_field = definition.get_content_field("TestCase")
    assert content_field == "test_content"
    
    # Verify field schema retrieval
    field_schema = definition.get_field_schema("TestCase", "status")
    assert field_schema["facet"] == "TestStatus"


def test_model_generation():
    """Test that models are generated correctly from archetypes."""
    definition = ArchetypeDefinition("../archetypes/test_fegis.yaml")
    
    # Generate model for TestCase mode
    model = ArchetypeModelGenerator.create_model_for_mode(definition, "TestCase")
    
    # Create a valid instance
    instance = model(
        test_title="Sample Test",
        test_content="This is a test case",
        status="pending",
        priority="medium",
        complexity="moderate",
        coverage="unit",
        reliability="stable",
        dependencies=["setup", "data"],
        tags=["regression", "api"]
    )
    
    # Verify the instance has the correct data
    assert instance.test_title == "Sample Test"
    assert instance.test_content == "This is a test case"
    assert instance.dependencies == ["setup", "data"]
    assert instance.tags == ["regression", "api"]


def test_optional_field_handling():
    """Test that optional fields without defaults are handled correctly."""
    definition = ArchetypeDefinition("../archetypes/test_fegis.yaml")
    
    # Generate model for TestResult mode which has fields with required: false and no default
    model = ArchetypeModelGenerator.create_model_for_mode(definition, "TestResult")
    
    # Create a minimal instance with only required fields
    instance = model(
        result_title="Test Result",
        result_content="This is a test result",
        test_reference="test-123",
        status="passed"
    )
    
    # Verify optional fields without defaults are set to None
    assert instance.error_message is None
    assert instance.artifacts is None
    assert instance.notes is None
    
    # Create an instance with optional fields specified
    instance_with_optionals = model(
        result_title="Test Result",
        result_content="This is a test result",
        test_reference="test-123",
        status="failed",
        error_message="Something went wrong",
        artifacts=["log.txt", "screenshot.png"],
        notes="Additional notes"
    )
    
    # Verify optional fields are set correctly when provided
    assert instance_with_optionals.error_message == "Something went wrong"
    assert instance_with_optionals.artifacts == ["log.txt", "screenshot.png"]
    assert instance_with_optionals.notes == "Additional notes"


def test_explicit_null_default_handling():
    """Test that fields with explicit null defaults are handled correctly."""
    # Create a test schema with a field that has explicit null default
    test_schema = {
        "modes": {
            "TestMode": {
                "fields": {
                    "required_field": {
                        "type": "str",
                        "required": True
                    },
                    "optional_with_null_default": {
                        "type": "str",
                        "required": False,
                        "default": None
                    },
                    "optional_without_default": {
                        "type": "str",
                        "required": False
                    }
                }
            }
        }
    }
    
    # Create a mock ArchetypeDefinition that returns our test schema
    class MockArchetypeDefinition:
        def get_mode_schema(self, mode_name):
            return test_schema["modes"][mode_name]
        
        def get_facet_schema(self, facet_name):
            return {}
    
    mock_definition = MockArchetypeDefinition()
    
    # Generate model for our test mode
    model = ArchetypeModelGenerator.create_model_for_mode(mock_definition, "TestMode")
    
    # Create an instance with only the required field
    instance = model(required_field="test")
    
    # Verify both optional fields are None, regardless of how they were defined
    assert instance.optional_with_null_default is None
    assert instance.optional_without_default is None
    
    # Verify we can set values for both optional fields
    instance_with_values = model(
        required_field="test",
        optional_with_null_default="value1",
        optional_without_default="value2"
    )
    
    assert instance_with_values.optional_with_null_default == "value1"
    assert instance_with_values.optional_without_default == "value2"


def test_field_metadata_access():
    """Test that field metadata is correctly stored and accessible."""
    definition = ArchetypeDefinition("../archetypes/test_fegis.yaml")
    
    # Generate model for TestCase mode
    model = ArchetypeModelGenerator.create_model_for_mode(definition, "TestCase")
    
    # Check that the field has the expected metadata
    # In Pydantic V2+, we need to access the field info differently
    field_info = model.model_fields["status"]
    
    # Verify the description is preserved
    assert field_info.description is not None
    
    # Verify the custom metadata is in json_schema_extra
    assert field_info.json_schema_extra is not None
    assert field_info.json_schema_extra.get("facet") == "TestStatus"


def test_artifact_field_mapper():
    """Test mapping between data and storage format."""
    definition = ArchetypeDefinition("../archetypes/test_fegis.yaml")
    
    # Sample data
    data = {
        "test_title": "Sample Test",
        "test_content": "This is a test case",
        "status": "pending",
        "priority": "medium",
        "complexity": "moderate",
        "coverage": "unit",
        "reliability": "stable",
        "dependencies": ["setup", "data"],
        "tags": ["regression", "api"]
    }
    
    # Map to storage format
    content, metadata = ArtifactFieldMapper.to_storage_format(
        definition, "TestCase", data
    )
    
    # Verify content extraction
    assert content == "This is a test case"
    
    # Verify metadata
    assert metadata["mode"] == "TestCase"
    assert "memory_id" in metadata["provenance"]
    assert metadata["facets"]["status"] == "pending"
    assert metadata["facets"]["priority"] == "medium"
    assert metadata["relata"]["dependencies"] == ["setup", "data"]
    assert metadata["relata"]["tags"] == ["regression", "api"]


@pytest.mark.asyncio
async def test_qdrant_storage_and_retrieval():
    """Test storing and retrieving data from Qdrant."""
    # Create in-memory client
    client = AsyncQdrantClient(":memory:")
    
    try:
        # Set up a test embedding model
        client.set_model("sentence-transformers/all-MiniLM-L6-v2")
        
        # Create a unique collection name
        collection_name = f"test_collection_{uuid.uuid4().hex}"
        
        # Create the collection
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=client.get_fastembed_vector_params()
        )
        
        # Test document
        test_doc = "This is a test document"
        test_metadata = {
            "mode": "Thought",
            "provenance": {"memory_id": str(uuid.uuid4())}
        }
        
        # Store the document
        await client.add(
            collection_name=collection_name,
            documents=[test_doc],
            metadata=[test_metadata]
        )
        
        # Search for the document
        results = await client.query(
            collection_name=collection_name,
            query_text="test document",
            limit=1
        )
        
        # Verify retrieval
        assert len(results) == 1
        assert results[0].document == "This is a test document"
    
    finally:
        # Clean up
        await client.close()
