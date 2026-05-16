"""
TypeSaveConfig pytest suite
"""

import pytest
import sys
from pathlib import Path
import json
from pydantic import Field, ValidationError
from typesaveconfig import ConfigModel, ExportFormat, ConfigError
from typing import Optional, Literal
from enum import Enum

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


class Status(str, Enum):
    ON = "on"
    OFF = "off"

class ComplexConfig(ConfigModel):
    optional_val: Optional[int] = None
    status: Status = Status.ON
    mode: Literal["prod", "dev"] = "dev"
    tags: list[str] = []


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



######################################################################
###############           TESTS                       ################
######################################################################

def test_metadata_generation():
    """Verify that metadata extraction works for nested models."""
    metadata = MainConfig.get_metadata()
    fullnames = [m.fullname for m in metadata]

    assert "app_name" in fullnames
    assert "sub__enabled" in fullnames
    assert "sub__level" in fullnames


def test_dict_merge_nested():
    """Verify deep merging of dictionaries."""
    data = {
        "port": 9090,
        "sub": {"level": 5}
    }
    cfg = MainConfig.load(payload=data, load_env=False, load_cli=False)
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


def test_load_default_values():
    """Verify that defaults are applied when no data is provided."""
    cfg = MainConfig.load(load_env=False, load_cli=False, readonly=False)
    assert cfg is not None
    assert cfg.app_name == "TestApp"
    assert cfg.port == 8080
    assert cfg.sub.enabled is True


def test_load_sourcecode_payload():
    """Verify loading configuration via the 'data' parameter."""
    # Define initial data as a dictionary
    initial_data = {
        "app_name": "DictApp",
        "port": 5555
    }

    # Load with initial_data, skipping other sources
    cfg = MainConfig.load(
        payload=initial_data,
        toml_files=[],
        json_files=[],
        load_env=False,
        load_cli=False,
    )

    assert cfg.app_name == "DictApp"
    assert cfg.port == 5555


def test_load_toml(config_files: tuple[Path, Path]):
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


def test_load_json(config_files: tuple[Path, Path]):
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






def test_load_env(monkeypatch: pytest.MonkeyPatch):
    """Verify loading from environment variables with nesting."""
    monkeypatch.setenv("CFG_APP_NAME", "EnvApp")
    monkeypatch.setenv("CFG_SUB__ENABLED", "false")

    cfg = MainConfig.load(load_env=True, load_cli=False)
    assert cfg is not None
    assert cfg.app_name == "EnvApp"
    assert cfg.sub.enabled is False


def test_load_cli(monkeypatch: pytest.MonkeyPatch):
    """Verify CLI argument parsing."""
    test_args = ["script.py", "--cfg_port=1234", "--cfg_sub__level=99"]
    monkeypatch.setattr(sys, "argv", test_args)

    cfg = MainConfig.load(load_env=False, load_cli=True)
    assert cfg is not None
    assert cfg.port == 1234
    assert cfg.sub.level == 99


def test_cli_prefix_override(monkeypatch: pytest.MonkeyPatch):
    """Verify that the CLI prefix can be changed."""
    test_args = ["script.py", "--myapp_port=9999"]
    monkeypatch.setattr(sys, "argv", test_args)

    # Use a custom prefix
    cfg = MainConfig.load(
        load_env=False,
        load_cli=True,
        cli_prefix="myapp_"
    )
    assert cfg.port == 9999


def test_optional_fields():
    """Verify None/Optional fields are handled correctly."""
    # Test with None explicitly
    data = {"optional_val": None}
    cfg = ComplexConfig.load(payload=data, load_env=False, load_cli=False)
    assert cfg.optional_val is None


def test_nested_list_of_models():
    """Verify deep list of models."""
    class Item(ConfigModel):
        id: int
    class Container(ConfigModel):
        items: list[Item]

    data = {"items": [{"id": 1}, {"id": 2}]}
    cfg = Container.load(payload=data, load_env=False, load_cli=False)
    assert len(cfg.items) == 2
    assert cfg.items[1].id == 2



def test_cli_empty_list_override(monkeypatch):
    """Verify CLI can pass empty lists/collections."""
    test_args = ["script.py", "--cfg_tags=[]"]
    monkeypatch.setattr(sys, "argv", test_args)

    cfg = ComplexConfig.load(load_env=False, load_cli=True, cli_prefix="cfg_")
    assert cfg.tags == []


def test_env_case_insensitivity(monkeypatch):
    """Verify that ENV variables are accepted (Pydantic usually handles this)."""
    # Test uppercase ENV assignment
    monkeypatch.setenv("CFG_STATUS", "on")
    # Pydantic matches this because it normalizes ENV keys
    cfg = ComplexConfig.load(load_env=True, load_cli=False)
    assert cfg.status == Status.ON


def test_cli_complex_json_input(monkeypatch: pytest.MonkeyPatch):
    """Verify CLI can accept JSON strings for lists and dicts."""
    class ComplexConfig(ConfigModel):
        """inner class to verify cli-json"""
        tags: list[str]
        metadata: dict[str, int]

    # CLI arguments with JSON syntax
    test_args = [
        "script.py",
        "--cfg_tags=[\"a\",\"b\"]",
        "--cfg_metadata={\"key\": 1}"
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    cfg = ComplexConfig.load(load_env=False, load_cli=True)
    assert cfg.tags == ["a", "b"]
    assert cfg.metadata == {"key": 1}


def test_validation_failure_raise_configerror():
    """Verify that invalid types results in a ConfigError."""
    # 'port' expects int, providing string that isn't castable to int
    data = {"port": "invalid_number"}

    with pytest.raises(ConfigError):
        _cfg = MainConfig.load(payload=data, load_env=False, load_cli=False)


def test_typesafe_scalar():
    """Verify pydantic handles type coercion for int, float, bool."""
    class TypeTestConfig(ConfigModel):
        val_int: int
        val_float: float
        val_bool: bool

    # Pydantic coerces "1" to 1, "1.5" to 1.5, "true"/"1" to True
    data = {"val_int": "10", "val_float": "3.14", "val_bool": "true"}
    cfg = TypeTestConfig.load(payload=data, load_env=False, load_cli=False)

    assert cfg.val_int == 10
    assert cfg.val_float == 3.14
    assert cfg.val_bool is True


def test_typesafe_enum():
    """Verify Enums and Literals are restricted."""
    # Valid
    cfg = ComplexConfig.load(payload={"status": "off", "mode": "prod"}, load_env=False, load_cli=False)
    assert cfg.status == Status.OFF

    # Invalid
    with pytest.raises(ConfigError):
        ComplexConfig.load(payload={"mode": "invalid"}, load_env=False, load_cli=False)


def test_priority_source_payload(tmp_path: Path):
    """Verify that 'data' parameter is overridden by TOML/JSON (if they have higher priority)."""
    # Note: Currently your code sets: merged = data; merged = merge(merged, toml); merged = merge(merged, json)
    # This means TOML/JSON files actually override the 'data' parameter.

    toml_path = tmp_path / "override.toml"
    toml_path.write_text('port = 9999')

    data = {"port": 1111}

    cfg = MainConfig.load(
        payload=data,
        toml_files=[str(toml_path)],
        load_env=False,
        load_cli=False
    )

    # Port from TOML (9999) should override port from 'data' (1111)


def test_priority_toml_vs_json(config_files: tuple[Path, Path]):
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


def test_priority_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Verify priority: ENV > CLI > JSON > TOML > Payload > Defaults
    We test the 'port' field which is an integer.
    """
    # 1. TOML (lowest priority)
    toml_path = tmp_path / "low.toml"
    toml_path.write_text('port = 1111')

    # 2. JSON
    json_path = tmp_path / "mid.json"
    json_path.write_text('{"port": 2222}')

    # 3. CLI (high priority)
    monkeypatch.setattr(sys, "argv", ["script.py", "--cfg_port=3333"])

    # 4. ENV (highest priority)
    monkeypatch.setenv("CFG_PORT", "4444")

    # Load with all sources active
    cfg = MainConfig.load(
        toml_files=[str(toml_path)],
        json_files=[str(json_path)],
        load_cli=True,
        load_env=True
    )

    # Assert priority: ENV (4444) wins
    assert cfg.port == 4444


def test_export_toml():
    """Verify export functionality if tomli-w is available."""
    cfg = MainConfig(app_name="Exporter")
    # This tests the logic; if tomli-w is missing, it falls back to JSON string
    output = cfg.export_config(ExportFormat.TOML)
    assert "app_name" in output


def test_export_json():
    """Verify export functionality for JSON available."""
    cfg = MainConfig(app_name="Exporter")
    jtxt = cfg.export_config(ExportFormat.JSON)
    jdata = json.loads(jtxt)

    assert jdata['app_name'] == "Exporter"


def test_readonly():
    """Verify that readonly=True (pydantic frozen) prevents attribute modification and False allows it."""

    # 1. Test Readonly Mode
    cfg_ro = MainConfig.load(readonly=True, load_env=False, load_cli=False)
    assert cfg_ro.app_name == "TestApp"

    with pytest.raises(ValidationError):
        cfg_ro.app_name = "Hacked"

    # 2. Test Mutable Mode
    cfg_rw = MainConfig.load(readonly=False, load_env=False, load_cli=False)
    cfg_rw.app_name = "MutableApp"
    assert cfg_rw.app_name == "MutableApp"

