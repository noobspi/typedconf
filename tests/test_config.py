"""
TypeSaveConfig pytest suite
"""

import pytest
import sys
from pathlib import Path
import json
from pydantic import Field, ValidationError
from typesaveconfig import ConfigModel, ExportFormat

# Testdata  Config-Schema
class SubConfig(ConfigModel):
    """Test Config-Schema - Sub Category"""
    enabled: bool = True
    level: int = 1

class MainConfig(ConfigModel):
    """Test Config-Schema - Main Category"""
    app_name: str = "TestApp"
    port: int = 8080
    tags: list[str] = Field(default_factory=list)
    sub: SubConfig = Field(default_factory=SubConfig)


@pytest.fixture
def config_files(tmp_path: Path):
    """Generates TOML and JSON files using the same schema structures."""
    # TOML File
    toml_path = tmp_path / "pytest_settings.toml"
    toml_content = """
    app_name = "TOML_App"
    port = 1111
    [sub]
    enabled = false
    level = 10
    """
    toml_path.write_text(toml_content, encoding="utf-8")

    # JSON File
    json_path = tmp_path / "pytest_settings.json"
    json_data = {
        "app_name": "JSON_App",
        "tags": ["json-tag"],
        "sub": {
            "level": 20
        }
    }
    json_path.write_text(json.dumps(json_data), encoding="utf-8")

    return toml_path, json_path


def test_default_values():
    """Verify that defaults are applied when no data is provided."""
    cfg = MainConfig.load(load_env=False, load_cli=False, readonly=False)
    assert cfg is not None
    assert cfg.app_name == "TestApp"
    assert cfg.port == 8080
    assert cfg.sub.enabled is True

def test_dict_merge_nested():
    """Verify deep merging of dictionaries."""
    data = {
        "port": 9090,
        "sub": {"level": 5}
    }
    cfg = MainConfig.load(data=data, load_env=False, load_cli=False)
    assert cfg is not None
    assert cfg.port == 9090
    assert cfg.sub.level == 5
    assert cfg.sub.enabled is True  # Should remain default

def test_readonly_immutability():
    """Verify that readonly=True prevents attribute modification."""
    cfg = MainConfig.load(readonly=True, load_env=False, load_cli=False)
    assert cfg is not None
    with pytest.raises(ValidationError):
        cfg.app_name = "NewName"

def test_env_loading(monkeypatch: pytest.MonkeyPatch):
    """Verify loading from environment variables with nesting."""
    monkeypatch.setenv("TSC_APP_NAME", "EnvApp")
    monkeypatch.setenv("TSC_SUB__ENABLED", "false")

    cfg = MainConfig.load(load_env=True, load_cli=False)
    assert cfg is not None
    assert cfg.app_name == "EnvApp"
    assert cfg.sub.enabled is False

def test_cli_loading(monkeypatch: pytest.MonkeyPatch):
    """Verify CLI argument parsing."""
    test_args = ["script.py", "--tsc_port=1234", "--tsc_sub__level=99"]
    monkeypatch.setattr(sys, "argv", test_args)

    cfg = MainConfig.load(load_env=False, load_cli=True)
    assert cfg is not None
    assert cfg.port == 1234
    assert cfg.sub.level == 99

def test_validation_failure_returns_none():
    """Verify that invalid types result in None return."""
    # 'port' expects int, providing string that isn't castable to int
    data = {"port": "invalid_number"}
    cfg = MainConfig.load(data=data, load_env=False, load_cli=False)
    assert cfg is None

def test_metadata_generation():
    """Verify that metadata extraction works for nested models."""
    metadata = MainConfig.get_metadata()
    fullnames = [m.fullname for m in metadata]

    assert "app_name" in fullnames
    assert "sub__enabled" in fullnames
    assert "sub__level" in fullnames

def test_toml_export():
    """Verify export functionality if tomli-w is available."""
    cfg = MainConfig(app_name="Exporter")
    # This tests the logic; if tomli-w is missing, it falls back to JSON string
    output = cfg.export(ExportFormat.TOML)
    assert "app_name" in output



def test_load_toml_full_schema(config_files: tuple[Path, Path]):
    """Verify TOML loading with nested SubConfig."""
    toml_path, _ = config_files

    cfg = MainConfig.load(
        toml_files=[str(toml_path)],
        load_env=False,
        load_cli=False
    )

    assert cfg is not None
    assert cfg.app_name == "TOML_App"
    assert cfg.port == 1111
    assert cfg.sub.enabled is False
    assert cfg.sub.level == 10

def test_load_json_full_schema(config_files: tuple[Path, Path]):
    """Verify JSON loading with nested SubConfig."""
    _, json_path = config_files

    cfg = MainConfig.load(
        json_files=[str(json_path)],
        load_env=False,
        load_cli=False
    )

    assert cfg is not None
    assert cfg.app_name == "JSON_App"
    assert cfg.tags == ["json-tag"]
    assert cfg.sub.enabled is True  # Default
    assert cfg.sub.level == 20

def test_merge_priority_toml_vs_json(config_files: tuple[Path, Path]):
    """
    Verify that JSON overrides TOML for specific fields while keeping unique fields from both.
    """
    toml_path, json_path = config_files

    # Order in load(): merged -> toml -> json
    cfg = MainConfig.load(
        toml_files=[str(toml_path)],
        json_files=[str(json_path)],
        load_env=False,
        load_cli=False
    )

    assert cfg is not None
    assert cfg.app_name == "JSON_App"  # JSON override
    assert cfg.port == 1111           # From TOML
    assert cfg.tags == ["json-tag"]    # From JSON
    assert cfg.sub.level == 20         # JSON override
    assert cfg.sub.enabled is False    # From TOML
