"""
TypedConfig pytest suite.
Validates loading, merging, validation, and immutability features.
"""

import pytest
import sys
import json
from pathlib import Path
from pydantic import Field, ValidationError
from typedconf import ConfigModel, ConfigError
from typing import Optional, Literal
from enum import Enum

# Check if optional python-package tomli-w is installed for export tests
IS_TOMLIW_INSTALLED: bool
try:
    import tomli_w
    IS_TOMLIW_INSTALLED = True
except ImportError:
    IS_TOMLIW_INSTALLED = False


# --- Test Schemas ---

class SubConfig(ConfigModel):
    """Configuration sub-schema for testing nested structures."""
    enabled: bool = True
    level: int = 1

class MainConfig(ConfigModel):
    """Main configuration schema used as the primary testing target."""
    app_name: str = "TestApp"
    port: int = 8080
    tags: list[str] = Field(default_factory=list)
    sub: SubConfig = Field(default_factory=SubConfig)

class Status(str, Enum):
    """Enum for testing type-safe restricted values."""
    ON = "on"
    OFF = "off"

class ComplexConfig(ConfigModel):
    """Schema for testing complex types, enums, and optional fields."""
    optional_val: Optional[int] = None
    status: Status = Status.ON
    mode: Literal["prod", "dev"] = "dev"
    tags: list[str] = []


# --- Fixtures ---

@pytest.fixture
def config_files(tmp_path: Path):
    """Generates temporary TOML and JSON files for file-loading tests."""
    toml_path = tmp_path / "settings.toml"
    toml_path.write_text('app_name = "TOML_App"\nport = 1111\n[sub]\nenabled = false\nlevel = 10', encoding="utf-8")

    json_path = tmp_path / "settings.json"
    json_path.write_text(json.dumps({"app_name": "JSON_App", "tags": ["json-tag"], "sub": {"level": 20}}), encoding="utf-8")

    return toml_path, json_path



################################################################################################
#######################      T E S T S      ####################################################
################################################################################################


# 1. Initialization and Metadata
def test_metadata_generation_basic():
    """Verify that metadata extraction identifies nested fields correctly."""
    metadata = MainConfig.get_metadata()
    fullnames = [m.fullname for m in metadata]
    assert "sub__enabled" in fullnames

def test_metadata_generation_deep_nesting():
    """Verify that metadata extraction works for 3+ levels of nesting."""
    class Deep(ConfigModel):
        val: int = 1
    class Mid(ConfigModel):
        d: Deep = Field(default_factory=Deep)
    class Root(ConfigModel):
        m: Mid = Field(default_factory=Mid)

    metadata = Root.get_metadata()
    assert any(m.fullname == "m__d__val" for m in metadata)

def test_help_cli_argument(monkeypatch):
    """Verify that --help flag."""
    monkeypatch.setattr(sys, "argv", ["script.py", "--help"])
    assert MainConfig.user_needs_help() is True

def test_help_cli_helptext():
    """Verify help text contains all nested fields"""
    class Deep(ConfigModel):
        val: int = 1
    class Mid(ConfigModel):
        val: int = 2
        d: Deep = Field(default_factory=Deep)
    class Root(ConfigModel):
        val: int = 3
        m: Mid = Field(default_factory=Mid)

    assert "--cfg_val" in Root.get_cli_helptext()
    assert "--cfg_m__val" in Root.get_cli_helptext()
    assert "--cfg_m__d__val" in Root.get_cli_helptext()



# 2. Loading Sources
def test_load_defaults():
    """Ensure schema defaults are applied correctly when no external data is provided."""
    cfg = MainConfig.load(load_env=False, load_cli=False, readonly=False)
    assert cfg.app_name == "TestApp"
    assert cfg.port == 8080

def test_load_payload():
    """Verify configuration loading via direct dictionary payload."""
    cfg = MainConfig.load(payload={"app_name": "DictApp"}, load_env=False, load_cli=False)
    assert cfg.app_name == "DictApp"

def test_load_toml(config_files):
    """Verify loading and parsing of TOML files."""
    toml_path, _ = config_files
    cfg = MainConfig.load(toml_files=[str(toml_path)], load_env=False, load_cli=False)
    assert cfg.app_name == "TOML_App"

def test_load_json(config_files):
    """Verify loading and parsing of JSON files."""
    _, json_path = config_files
    cfg = MainConfig.load(json_files=[str(json_path)], load_env=False, load_cli=False)
    assert cfg.app_name == "JSON_App"

def test_load_env(monkeypatch):
    """Verify that environment variables are loaded with prefix support."""
    monkeypatch.setenv("CFG_APP_NAME", "EnvApp")
    cfg = MainConfig.load(load_env=True, load_cli=False)
    assert cfg.app_name == "EnvApp"

def test_load_cli(monkeypatch):
    """Verify that basic CLI arguments are correctly parsed."""
    monkeypatch.setattr(sys, "argv", ["script.py", "--cfg_port=1234"])
    cfg = MainConfig.load(load_env=False, load_cli=True)
    assert cfg.port == 1234

def test_prefix_override_cli(monkeypatch):
    """Verify that the CLI prefix can be changed to a custom value."""
    monkeypatch.setattr(sys, "argv", ["script.py", "--myapp_port=9999"])
    cfg = MainConfig.load(load_env=False, load_cli=True, cli_prefix="myapp_")
    assert cfg.port == 9999

def test_prefix_override_env(monkeypatch):
    """Verify that the ENV prefix can be changed to a custom value."""
    monkeypatch.setenv("MYAPP_PORT", "9999")
    cfg = MainConfig.load(load_env=True, load_cli=False, cli_prefix="myapp_")
    assert cfg.port == 9999


# 3. Data Integrity and Validation
def test_validation_typesafe_scalar():
    """Verify that scalars are correctly coerced by Pydantic."""
    class TypeTest(ConfigModel):
        val_int: int
    cfg = TypeTest.load(payload={"val_int": "10"}, load_env=False, load_cli=False)
    assert cfg.val_int == 10

def test_validation_enum_restriction():
    """Verify that restricted Enum values raise ConfigError when invalid."""
    with pytest.raises(ConfigError):
        ComplexConfig.load(payload={"mode": "invalid"}, load_env=False, load_cli=False)

def test_validation_missing_required_field():
    """Verify that missing fields without defaults raise ConfigError."""
    class Missing(ConfigModel):
        val: int
    with pytest.raises(ConfigError):
        Missing.load(payload={}, load_env=False, load_cli=False)

def test_validation_malformed_cli_list(monkeypatch):
    """Verify that invalid JSON syntax in CLI arguments raises ConfigError."""
    monkeypatch.setattr(sys, "argv", ["script.py", "--cfg_tags=[1, invalid]"])
    with pytest.raises(ConfigError):
        ComplexConfig.load(load_env=False, load_cli=True)

def test_validation_malformed_cli_dict(monkeypatch):
    """Verify that CLI can accept complex JSON strings for lists and dictionaries."""
    class Complex(ConfigModel):
        tags: list[str]
        metadata: dict[str, int]

    test_args = ["script.py", "--cfg_tags=[\"a\",\"b\"]", "--cfg_metadata={\"key\": 1}"]
    monkeypatch.setattr(sys, "argv", test_args)
    cfg = Complex.load(load_env=False, load_cli=True)
    assert cfg.tags == ["a", "b"]
    assert cfg.metadata == {"key": 1}

# 4. Priority and Merging
def test_priority_json_overrides_toml(config_files):
    """Verify that JSON file data takes precedence over TOML file data."""
    toml, json_path = config_files
    cfg = MainConfig.load(toml_files=[str(toml)], json_files=[str(json_path)], load_env=False, load_cli=False)
    assert cfg.app_name == "JSON_App"

def test_priority_chain_full(tmp_path, monkeypatch):
    """Verify the full hierarchy: ENV > CLI > JSON > TOML > Payload > Defaults."""
    toml = tmp_path / "l.toml"; toml.write_text('port = 1111')
    json_f = tmp_path / "m.json"; json_f.write_text('{"port": 2222}')
    monkeypatch.setattr(sys, "argv", ["s.py", "--cfg_port=3333"])
    monkeypatch.setenv("CFG_PORT", "4444")

    cfg = MainConfig.load(toml_files=[str(toml)], json_files=[str(json_f)], load_cli=True, load_env=True)
    assert cfg.port == 4444

# 5. Robustness and Error Handling
def test_robustness_malformed_toml(tmp_path):
    """Verify that syntactically incorrect TOML files are handled gracefully."""
    f = tmp_path / "bad.toml"; f.write_text("port = [err")
    cfg = MainConfig.load(toml_files=[str(f)], load_env=False, load_cli=False)
    assert cfg.port == 8080

def test_robustness_malformed_json(tmp_path):
    """Verify that syntactically incorrect JSON files are handled gracefully."""
    f = tmp_path / "bad.json"; f.write_text('{"port": "err"')
    cfg = MainConfig.load(json_files=[str(f)], load_env=False, load_cli=False)
    assert cfg.port == 8080

def test_robustness_missing_toml():
    """Verify that missing TOML files do not interrupt configuration loading."""
    assert MainConfig.load(toml_files=["no.toml"], load_env=False, load_cli=False) is not None

def test_robustness_missing_json():
    """Verify that missing JSON files do not interrupt configuration loading."""
    assert MainConfig.load(json_files=["no.json"], load_env=False, load_cli=False) is not None

def test_robustness_partial_nested_update():
    """Verify that providing partial nested data keeps defaults for the rest."""
    payload = {"sub": {"enabled": False}} # 'level' is missing, should remain at default
    cfg = MainConfig.load(payload=payload, load_env=False, load_cli=False)
    assert cfg.sub.enabled is False
    assert cfg.sub.level == 1  # Default kept

def test_robustness_list_override_behavior():
    """Verify that lists are replaced (not appended) during deep merge."""
    data_a = {"tags": ["a"]}
    data_b = {"tags": ["b"]}
    merged = MainConfig._deep_merge(data_a, data_b)
    assert merged["tags"] == ["b"]

def test_robustness_class_isolation():
    """Verify that metadata from one class does not leak to another."""
    class ConfigA(ConfigModel):
        field_a: int = 1
    class ConfigB(ConfigModel):
        field_b: int = 2

    assert any(m.name == "field_a" for m in ConfigA.get_metadata())
    assert not any(m.name == "field_a" for m in ConfigB.get_metadata())

# 6. Immutability and Export
def test_readonly():
    """Verify that readonly mode prevents attribute modification."""
    class ConfigA(ConfigModel):
        a: int = 1
    cfg = ConfigA.load(readonly=True, load_env=False, load_cli=False)
    with pytest.raises(ValidationError):
        cfg.a = 2
    assert cfg.a == 1

def test_writeable():
    """Verify that write mode accept attribute modification."""
    class ConfigA(ConfigModel):
        a: int = 1
    cfg = ConfigA.load(readonly=False, load_env=False, load_cli=False)
    cfg.a = 2
    assert cfg.a == 2

def test_export_json_serialization():
    """Verify that the configuration can be exported to JSON."""
    cfg = MainConfig(app_name="Exp")
    assert json.loads(cfg.dumps_json())['app_name'] == "Exp"

@pytest.mark.skipif(not IS_TOMLIW_INSTALLED, reason="tomli_w missing")
def test_export_toml_serialization():
    """Verify that the configuration can be exported to TOML."""
    cfg = MainConfig(app_name="Exp")
    assert "app_name" in str(cfg.dumps_toml())
