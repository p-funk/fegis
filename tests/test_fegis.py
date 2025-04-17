"""
YAML-driven tests for FEGIS server components.

These tests verify the core functionality by using the actual YAML configuration files
rather than hardcoded test expectations.
"""

import glob
import os
import uuid
from pathlib import Path

import pytest
import yaml
from mcp_fegis_server.constants import MODE_FIELD, ARTIFACT_ID_FIELD, CREATED_AT_FIELD, TITLE_FIELD
from mcp_fegis_server.model_builder import ArchetypeDefinition, ArchetypeModelGenerator, ArtifactFieldMapper
from qdrant_client import AsyncQdrantClient


# Helper function to find all YAML config files
def find_yaml_configs(directory="../archetypes"):
    """Find all YAML configuration files in the given directory."""
    yaml_files = glob.glob(os.path.join(directory, "*.yaml"))
    if not yaml_files:
        pytest.skip(f"No YAML files found in {directory}")
    return yaml_files


def test_archetype_definition_loads_yaml():
    """Test that ArchetypeDefinition can load all YAML files."""
    yaml_files = find_yaml_configs()

    for yaml_file in yaml_files:
        # Test that the file can be loaded without errors
        definition = ArchetypeDefinition(yaml_file)

        # Basic assertions to verify the file loaded
        assert definition.modes, f"No modes found in {yaml_file}"
        assert definition.raw, f"Failed to load {yaml_file}"

        # Verify the YAML structure matches what we expect
        assert "modes" in definition.raw, f"Missing 'modes' section in {yaml_file}"


@pytest.mark.parametrize("yaml_file", find_yaml_configs())
def test_modes_from_yaml(yaml_file):
    """Test that modes from YAML files are correctly parsed."""
    definition = ArchetypeDefinition(yaml_file)

    # Load the raw YAML for comparison
    with open(yaml_file, 'r', encoding='utf-8') as f:
        raw_yaml = yaml.safe_load(f)

    # Verify that all modes in the YAML are exposed by the API
    expected_modes = list(raw_yaml.get("modes", {}).keys())
    actual_modes = definition.modes

    assert set(actual_modes) == set(expected_modes), f"Mode mismatch in {yaml_file}"

    # Test content field detection for each mode
    for mode in actual_modes:
        mode_schema = raw_yaml["modes"][mode]

        # If content_field is explicitly defined
        if "content_field" in mode_schema:
            expected_content_field = mode_schema["content_field"]
            assert definition.content_field(mode) == expected_content_field, \
                f"Content field mismatch for {mode} in {yaml_file}"

        # If we need to infer it from field names ending with _content
        else:
            content_fields = [
                field for field in mode_schema.get("fields", {})
                if field.endswith("_content")
            ]
            if content_fields:
                # Assert that content_field returns the expected field
                assert definition.content_field(mode) in content_fields, \
                    f"Inferred content field mismatch for {mode} in {yaml_file}"


@pytest.mark.parametrize("yaml_file", find_yaml_configs())
def test_model_generation_from_yaml(yaml_file):
    """Test that models are correctly generated from YAML configurations."""
    definition = ArchetypeDefinition(yaml_file)

    for mode in definition.modes:
        # Generate model for the mode
        model = ArchetypeModelGenerator.create(definition, mode)

        # Get the fields from the mode schema
        mode_schema = definition.mode_schema(mode)
        expected_fields = mode_schema.get("fields", {})

        # Verify that the model has fields for each field in the schema
        for field_name in expected_fields:
            assert field_name in model.model_fields, \
                f"Field {field_name} missing from generated model for {mode} in {yaml_file}"

            # Check field requirements match
            field_spec = expected_fields[field_name]
            is_required = field_spec.get("required", False)

            # In Pydantic v2, check if the field has a default value
            if is_required:
                assert model.model_fields[field_name].is_required(), \
                    f"Field {field_name} should be required for {mode} in {yaml_file}"


@pytest.mark.parametrize("yaml_file", find_yaml_configs())
def test_facets_from_yaml(yaml_file):
    """Test that facets from YAML are correctly parsed and used."""
    definition = ArchetypeDefinition(yaml_file)

    # Load the raw YAML for comparison
    with open(yaml_file, 'r', encoding='utf-8') as f:
        raw_yaml = yaml.safe_load(f)

    # Verify facets are correctly loaded
    expected_facets = raw_yaml.get("facets", {})

    # Check each facet is available through the API
    for facet_name, facet_spec in expected_facets.items():
        assert definition.facet_schema(facet_name) == facet_spec, \
            f"Facet {facet_name} mismatch in {yaml_file}"

    # Check that facet examples are included in generated models
    for mode in definition.modes:
        # Find fields with facets
        mode_schema = definition.mode_schema(mode)
        fields_with_facets = {
            field_name: field_spec.get("facet")
            for field_name, field_spec in mode_schema.get("fields", {}).items()
            if field_spec.get("facet") is not None
        }

        if fields_with_facets:
            # Generate the model
            model = ArchetypeModelGenerator.create(definition, mode)

            # Check that facet info is included in the model
            for field_name, facet_name in fields_with_facets.items():
                field_info = model.model_fields[field_name]
                assert field_info.json_schema_extra, \
                    f"Missing json_schema_extra for {field_name} in {mode} model"
                assert field_info.json_schema_extra.get("facet") == facet_name, \
                    f"Facet name mismatch for {field_name} in {mode} model"

                # If the facet has examples, check if they're included
                facet_examples = expected_facets.get(facet_name, {}).get("facet_examples")
                if facet_examples:
                    assert field_info.json_schema_extra.get("facet_examples") == facet_examples, \
                        f"Facet examples mismatch for {field_name} in {mode} model"


@pytest.mark.parametrize("yaml_file", find_yaml_configs())
def test_storage_mapping_from_yaml(yaml_file):
    """Test that data is correctly mapped to storage format based on YAML config."""
    definition = ArchetypeDefinition(yaml_file)

    for mode in definition.modes:
        # Get the content field for this mode
        content_field = definition.content_field(mode)
        if not content_field:
            continue  # Skip modes without content fields

        # Generate sample data for this mode
        mode_schema = definition.mode_schema(mode)
        sample_data = {}

        # Create sample data for all required fields and some optional ones
        for field_name, field_spec in mode_schema.get("fields", {}).items():
            field_type = field_spec.get("type", "str")

            # Generate appropriate sample data based on type
            if field_type == "str":
                sample_data[field_name] = f"Sample {field_name}"
            elif field_type == "List[str]":
                sample_data[field_name] = [f"item1_{field_name}", f"item2_{field_name}"]
            elif field_type == "int":
                sample_data[field_name] = 42
            elif field_type == "float":
                sample_data[field_name] = 3.14
            elif field_type == "bool":
                sample_data[field_name] = True

        # Map to storage format
        content, metadata = ArtifactFieldMapper.to_storage(definition, mode, sample_data)

        # Verify the content matches what we expect
        assert content == sample_data[content_field], \
            f"Content mismatch for {mode} in {yaml_file}"

        # Basic metadata checks
        assert metadata[MODE_FIELD] == mode, \
            f"Mode field mismatch in metadata for {mode} in {yaml_file}"
        assert "provenance" in metadata, \
            f"Missing provenance in metadata for {mode} in {yaml_file}"
        assert "artifact_id" in metadata["provenance"], \
            f"Missing artifact_id in metadata for {mode} in {yaml_file}"

        # Check that all facet fields are correctly mapped
        facet_fields = {
            field_name: field_spec.get("facet")
            for field_name, field_spec in mode_schema.get("fields", {}).items()
            if field_spec.get("facet") and field_name in sample_data
        }

        for field_name, facet_name in facet_fields.items():
            assert metadata["facets"][field_name] == sample_data[field_name], \
                f"Facet field {field_name} mismatch in metadata for {mode} in {yaml_file}"

        # Check that all relata fields are correctly mapped
        relata_fields = [
            field_name
            for field_name, field_spec in mode_schema.get("fields", {}).items()
            if field_spec.get("type") == "List[str]" and field_name in sample_data
        ]

        for field_name in relata_fields:
            if field_name in metadata["relata"]:
                assert metadata["relata"][field_name] == sample_data[field_name], \
                    f"Relata field {field_name} mismatch in metadata for {mode} in {yaml_file}"


def test_artifact_field_mapper():
    """Test that ArtifactFieldMapper correctly transforms input data to storage format."""
    # Use a specific YAML file
    yaml_file = Path(__file__).parent.parent / "archetypes" / "slime_mold.yaml"
    assert yaml_file.exists(), f"YAML file not found: {yaml_file}"
    
    definition = ArchetypeDefinition(str(yaml_file))
    mode = definition.modes[0]  # Use the first mode
    
    # Get the content field
    content_field = definition.content_field(mode)
    assert content_field, f"No content field found for mode {mode}"
    
    # Create sample data with all required fields
    sample_data = {content_field: f"This is a test document for {mode}"}
    mode_schema = definition.mode_schema(mode)
    
    # Add required fields
    for field_name, field_spec in mode_schema.get("fields", {}).items():
        if field_spec.get("required", False) and field_name != content_field:
            if field_spec.get("type") == "List[str]":
                sample_data[field_name] = ["test_item"]
            else:
                sample_data[field_name] = f"test_{field_name}"
    
    # Map to storage format
    content, metadata = ArtifactFieldMapper.to_storage(definition, mode, sample_data)
    
    # Verify the mapping is correct
    assert content == sample_data[content_field], f"Content mismatch: expected {sample_data[content_field]}, got {content}"
    assert metadata[MODE_FIELD] == mode, f"Mode field mismatch: expected {mode}, got {metadata[MODE_FIELD]}"
    assert "provenance" in metadata, "Missing provenance in metadata"
    assert "artifact_id" in metadata["provenance"], "Missing artifact_id in metadata"
    assert "created_at" in metadata["provenance"], "Missing created_at in metadata"
    
    # Check that all facet fields are correctly mapped
    facet_fields = {
        field_name: field_spec.get("facet")
        for field_name, field_spec in mode_schema.get("fields", {}).items()
        if field_spec.get("facet") and field_name in sample_data
    }
    
    for field_name, facet_name in facet_fields.items():
        assert field_name in metadata["facets"], f"Facet field {field_name} missing from metadata"
        assert metadata["facets"][field_name] == sample_data[field_name], \
            f"Facet field {field_name} mismatch: expected {sample_data[field_name]}, got {metadata['facets'][field_name]}"
    
    # Check that all relata fields are correctly mapped
    relata_fields = [
        field_name
        for field_name, field_spec in mode_schema.get("fields", {}).items()
        if field_spec.get("type") == "List[str]" and field_name in sample_data
    ]
    
    for field_name in relata_fields:
        assert field_name in metadata["relata"], f"Relata field {field_name} missing from metadata"
        assert metadata["relata"][field_name] == sample_data[field_name], \
            f"Relata field {field_name} mismatch: expected {sample_data[field_name]}, got {metadata['relata'][field_name]}"
