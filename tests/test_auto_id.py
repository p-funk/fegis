"""
Tests for the auto-ID functionality in FEGIS.
"""
import uuid
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from fegis.archetype_compiler import ArtifactFieldMapper
from fegis.constants import TOOL_NAME, TIMESTAMP, USE_TITLE
from fegis.qdrant_connector import QdrantConnector
from fegis.settings import QdrantSettings


@pytest.fixture
def mock_schema():
    """Create a mock schema for testing."""
    schema = MagicMock()
    # No global processes by default
    schema.processes.return_value = {}
    # Each tool has no extra processes or frames
    schema.tool.return_value = MagicMock(processes={}, frames={})
    # Define which key holds the content and which holds the title
    schema.content_field.return_value = "test_content"
    schema.use_title_field.return_value = "test_title"
    return schema


@pytest.fixture
def mock_qdrant_settings():
    """Create mock QdrantSettings."""
    settings = MagicMock(spec=QdrantSettings)
    settings.qdrant_url = "http://localhost:6333"
    settings.qdrant_api_key = None
    settings.collection_name = "test_collection"
    settings.fast_embed_model = "test_model"
    settings.use_auto_id = True  # This is now always True in the actual code
    return settings


def test_artifact_field_mapper_no_artifact_id(mock_schema):
    """Test that ArtifactFieldMapper.to_storage doesn't add artifact_id."""
    data = {
        "test_title": "Test Title",
        "test_content": "Test Content",
    }

    content, meta = ArtifactFieldMapper.to_storage(mock_schema, "TestTool", data)

    # Verify content is extracted correctly
    assert content == "Test Content"

    # Verify metadata structure
    assert meta[TOOL_NAME] == "TestTool"
    assert meta[USE_TITLE] == "Test Title"
    assert TIMESTAMP in meta
    assert "processes" in meta
    assert "frames" in meta

    # Verify artifact_id is not in metadata
    assert "artifact_id" not in meta


@pytest.mark.asyncio
async def test_auto_id_returns_uuid(mock_schema, mock_qdrant_settings):
    """Test that auto-ID returns a UUID from Qdrant."""
    # Mock AsyncQdrantClient
    mock_client = MagicMock()
    mock_client.add = AsyncMock(return_value=["test-uuid-123"])

    with patch("fegis.qdrant_connector.QdrantClientSingleton") as mock_singleton:
        mock_singleton.get_instance.return_value = mock_client

        connector = QdrantConnector(mock_qdrant_settings, mock_schema)
        connector._ready = True  # Skip initialization

        async def process_tool(tool, data):
            content, meta = ArtifactFieldMapper.to_storage(mock_schema, tool, data)
            ids = await connector.client.add(
                collection_name=connector.col,
                documents=[content],
                metadata=[meta],
            )
            return {"stored": tool, "artifact_uuid": ids[0]}

        result = await process_tool("TestTool", {
            "test_title": "Test Title",
            "test_content": "Test Content",
        })

        assert result["stored"] == "TestTool"
        assert result["artifact_uuid"] == "test-uuid-123"

        mock_client.add.assert_called_once()
        _, kwargs = mock_client.add.call_args
        assert kwargs["collection_name"] == "test_collection"
        assert len(kwargs["documents"]) == 1
        assert len(kwargs["metadata"]) == 1
        assert "ids" not in kwargs


@pytest.mark.asyncio
async def test_retrieve_with_point_id(mock_schema, mock_qdrant_settings):
    """Test retrieving a document using point ID."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.payload = {
        "content": "Test Content",
        "meta": {"title": "Test Title"}
    }
    mock_client.retrieve = AsyncMock(return_value=[mock_response])

    with patch("fegis.qdrant_connector.QdrantClientSingleton") as mock_singleton:
        mock_singleton.get_instance.return_value = mock_client

        connector = QdrantConnector(mock_qdrant_settings, mock_schema)
        connector._ready = True

        async def retrieve_memory(artifact_uuid):
            res = await connector.client.retrieve(
                collection_name=connector.col,
                ids=[artifact_uuid],
                with_vectors=False
            )
            if not res:
                return {"error": "Not found"}
            r = res[0]
            return {
                "artifact": {
                    "content": r.payload["content"],
                    "meta":    r.payload["meta"]
                }
            }

        result = await retrieve_memory("test-uuid-123")
        assert "artifact" in result
        mock_client.retrieve.assert_called_once_with(
            collection_name="test_collection",
            ids=["test-uuid-123"],
            with_vectors=False
        )


@pytest.mark.asyncio
async def test_roundtrip_store_retrieve(mock_schema, mock_qdrant_settings):
    """Test a full roundtrip of storing and retrieving a document."""
    mock_client = MagicMock()
    test_uuid = "test-uuid-456"
    test_content = "Test Content for Roundtrip"
    test_title = "Roundtrip Test"

    mock_client.add = AsyncMock(return_value=[test_uuid])
    mock_response = MagicMock()
    mock_response.payload = {
        "content": test_content,
        "meta": {"title": test_title}
    }
    mock_client.retrieve = AsyncMock(return_value=[mock_response])

    with patch("fegis.qdrant_connector.QdrantClientSingleton") as mock_singleton:
        mock_singleton.get_instance.return_value = mock_client

        connector = QdrantConnector(mock_qdrant_settings, mock_schema)
        connector._ready = True

        async def process_mode(mode, data):
            content, meta = ArtifactFieldMapper.to_storage(mock_schema, mode, data)
            ids = await connector.client.add(
                collection_name=connector.col,
                documents=[content],
                metadata=[meta],
            )
            return {"stored": mode, "artifact_uuid": ids[0]}

        async def retrieve_memory(artifact_uuid):
            res = await connector.client.retrieve(
                collection_name=connector.col,
                ids=[artifact_uuid],
                with_vectors=False
            )
            if not res:
                return {"error": "Not found"}
            r = res[0]
            return {
                "artifact": {
                    "content": r.payload["content"],
                    "meta":    r.payload["meta"]
                }
            }

        store_result = await process_mode("TestTool", {
            "test_title": test_title,
            "test_content": test_content,
        })
        assert store_result["stored"] == "TestTool"
        assert store_result["artifact_uuid"] == test_uuid

        retrieve_result = await retrieve_memory(store_result["artifact_uuid"])
        assert retrieve_result["artifact"]["content"] == test_content
        assert retrieve_result["artifact"]["meta"]["title"] == test_title
