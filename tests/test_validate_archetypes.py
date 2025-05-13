# test_archetype_validation.py
import pytest
from pathlib import Path
from fegis.archetype_compiler import ArchetypeDefinition

ARCHETYPE_DIR = Path("archetypes")
yaml_files = list(ARCHETYPE_DIR.rglob("*.yaml")) + list(ARCHETYPE_DIR.rglob("*.yml"))

@pytest.mark.parametrize("yaml_file", yaml_files)
def test_archetype_validates_with_clear_errors(yaml_file):
    try:
        _ = ArchetypeDefinition(yaml_file)
    except Exception as e:
        msg = f"""
❌ Archetype failed to compile: {yaml_file.name}
──────────────────────────────────────────────
{str(e)}
──────────────────────────────────────────────
Check that:
- All required top-level fields are present (version, title, parameters, tools)
- Each parameter has a description and example_values
- Each tool has at least one frame
- All referenced parameters are defined
"""
        pytest.fail(msg)
