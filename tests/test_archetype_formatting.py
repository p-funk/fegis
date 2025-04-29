# tests/test_archetype_formatting.py

import pytest
import yaml
from pathlib import Path
from fegis.archetype_compiler import ArchetypeDefinition, ArchetypeModelGenerator
from pydantic import ValidationError
from typing import Union, get_type_hints, get_args, get_origin

# -------------------------------------------------------------------
# 1) Figure out project root and locate archetype(s) folder
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

for dname in ("archetype", "archetypes"):
    candidate = PROJECT_ROOT / dname
    if candidate.exists() and candidate.is_dir():
        ARCHETYPE_DIR = candidate
        break
else:
    pytest.exit(
        "❌ Could not find an 'archetype/' or 'archetypes/' directory next to tests/.\n"
        f"Searched in: {PROJECT_ROOT}",
        returncode=1
    )

# -------------------------------------------------------------------
# 2) Glob all .yaml files, or skip if none
# -------------------------------------------------------------------
yaml_files = sorted(ARCHETYPE_DIR.glob("*.yaml"))
if not yaml_files:
    pytest.skip(f"No .yaml files found in {ARCHETYPE_DIR}", allow_module_level=True)

# -------------------------------------------------------------------
# 3) YAML formatting/structure validation
# -------------------------------------------------------------------
REQUIRED_TOP_LEVEL_KEYS = {"version", "title", "priming_prompt", "processes", "tools"}


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_archetype(data: dict) -> list[str]:
    errors: list[str] = []

    # Top-level structure
    missing = REQUIRED_TOP_LEVEL_KEYS - data.keys()
    if missing:
        errors.append(f"Missing top-level keys: {sorted(missing)}")

    # Facets definitions
    known_frames = set()
    for name, frame in data.get("processes", {}).items():
        known_frames.add(name)
        if "description" not in frame:
            errors.append(f"Facet '{name}' missing 'description'")
        if "illustrative_options" not in frame:
            errors.append(f"Facet '{name}' missing 'illustrative_options'")

    # Tools
    for mode_name, mode in data.get("tools", {}).items():
        if "description" not in mode:
            errors.append(f"Tool '{mode_name}' missing 'description'")

        # processes block
        if "processes" not in mode:
            errors.append(f"Tool '{mode_name}' missing 'processes' block")
        else:
            frames_block = mode["processes"]
            if not frames_block:
                errors.append(f"Tool '{mode_name}' has an empty 'processes' block")
            else:
                for field, fval in frames_block.items():
                    # **allow shorthand** (e.g. Complexity: moderate)
                    if not isinstance(fval, dict):
                        # shorthand is valid: frame name==field, default==fval
                        continue

                    # full syntax: must have a 'facet' key
                    if "frame" not in fval:
                        errors.append(f"Tool '{mode_name}' frame '{field}' missing 'frame' key")
                    elif fval["frame"] not in known_frames:
                        errors.append(
                            f"Tool '{mode_name}' frame '{field}' references unknown frame '{fval['frame']}'"
                        )

        # frames block
        if "frames" not in mode:
            errors.append(f"Tool '{mode_name}' missing 'frames' block")
        elif not mode["frames"]:
            errors.append(f"Tool '{mode_name}' has an empty 'frames' block")

    return errors


@pytest.mark.parametrize("yaml_file", yaml_files)
def test_archetype_formatting(yaml_file: Path):
    print(f"\n🧪 Validating: {yaml_file.relative_to(PROJECT_ROOT)}")
    try:
        data = load_yaml(yaml_file)
        errors = validate_archetype(data)

        if errors:
            print("❌ FAIL")
            for err in errors:
                print(f"   - {err}")
        else:
            print("✅ PASS")

        assert not errors, f"{yaml_file.name} failed validation with {len(errors)} error(s)."
    except yaml.scanner.ScannerError as e:
        # Add more context about the error location
        print(f"❌ YAML Syntax Error in {yaml_file.name}: {e}")
        pytest.fail(f"YAML syntax error in {yaml_file.name}: {e}")


# -------------------------------------------------------------------
# 4) Compilation + Pydantic model instantiation tests
# -------------------------------------------------------------------
@pytest.mark.parametrize("yaml_file", yaml_files)
def test_archetype_compiles_and_models_load(yaml_file: Path):
    # Load via the real compiler
    schema = ArchetypeDefinition(yaml_file)
    assert schema.archetype.title

    # For each tool, generate and instantiate a Pydantic model
    for tool_name in schema.tools():
        ModelCls = ArchetypeModelGenerator.create(schema, tool_name)

        # Build the minimal payload
        init_data: dict = {}
        init_data[schema.use_title_field(tool_name)] = f"{tool_name} tool_use_summary"
        init_data[schema.content_field(tool_name)] = f"{tool_name} content"

        # Fill any other required fields
        for fname, field in ModelCls.model_fields.items():
            if field.is_required and fname not in init_data:
                # Get the annotation type - Pydantic v2 compatible
                annotation_type = field.annotation

                # String → dummy
                if annotation_type is str or (
                        hasattr(annotation_type, "__origin__") and
                        get_origin(annotation_type) is Union and
                        str in get_args(annotation_type)
                ):
                    init_data[fname] = "x"
                # List → single-item list
                elif hasattr(annotation_type, "__origin__") and get_origin(annotation_type) is list:
                    init_data[fname] = ["x"]
                # Bool → True
                elif annotation_type is bool:
                    init_data[fname] = True
                # Float → 1.0
                elif annotation_type is float:
                    init_data[fname] = 1.0
                # Integer → 1
                elif annotation_type is int:
                    init_data[fname] = 1
                # For any other type, try a placeholder value or skip
                else:
                    print(f"Warning: Unknown field type for {fname}: {annotation_type}")

        # Attempt instantiation
        try:
            inst = ModelCls(**init_data)
        except ValidationError as e:
            pytest.fail(f"Tool '{tool_name}' model validation failed: {e}")

        # Sanity checks
        assert getattr(inst, schema.use_title_field(tool_name)) == init_data[schema.use_title_field(tool_name)]
        assert getattr(inst, schema.content_field(tool_name)) == init_data[schema.content_field(tool_name)]