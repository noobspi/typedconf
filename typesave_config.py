"""
# TypeSaveConfig

A lightweight, type-safe configuration management library powered by Pydantic v2.
It centralizes application settings by merging data from multiple sources with a
defined priority (Environment > CLI > JSON > TOML > Defaults).

## Key Features:
- **Automatic Merging**: Priority-based merging of various config sources.
- **Deep Nesting**: Supports nested Pydantic models using `__` as a separator.
- **Type Safety**: Full validation of types, including lists and Enums.
- **Optional Dependencies**: Enhanced output via `rich`, `.env` support via `python-dotenv`,
  and TOML exporting via `tomli-w`.
- **Immutability**: Config can be optionally 'frozen' (readonly) after loading.

## Usage Example:
    class MyConfig(ConfigModel):
        db_url: str = "localhost"
        debug: bool = False

    # Load from all sources with default prefix 'TSC_'
    cfg = MyConfig.load(toml_files=["config.toml"])

    # Access values
    print(cfg.db_url)

## CLI & Env Syntax:
- **Environment**: `export TSC_DB_URL="postgres://..."`
- **CLI**: `python script.py --tsc_db_url="postgres://..."`
- **Lists (CLI)**: `--tsc_tags='["a", "b"]'` (Uses JSON-style parsing)
"""

import json
import logging
import os
import sys
import tomllib
from enum import Enum
from pathlib import Path
from typing import Any, Type, TypeVar, Union, get_args, Optional

from pydantic import BaseModel, ValidationError

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class _LibWrapper:
    """
    Internal abstraction for optional third-party libraries.
    Ensures the library remains functional even if 'rich', 'python-dotenv',
    or 'tomli-w' are not installed.
    """
    def __init__(self):
        self.rich, self.has_rich = self._import("rich")
        self.dotenv, self.has_dotenv = self._import("dotenv")
        self.tomli_w, self.has_tomliw = self._import("tomli_w")

        installed = []
        if self.has_rich:
            installed.append("rich")
        if self.has_dotenv:
            installed.append("python-dotenv")
        if self.has_tomliw:
            installed.append("tomli-w")

        status_str = ", ".join(installed) if installed else "none"
        logging.debug("🔧 [TypeSaveConfig] Extra libraries installed: %s", status_str)

    @staticmethod
    def _import(name: str):
        try:
            return __import__(name), True
        except ImportError:
            return None, False

    def load_dotenv(self) -> None:
        """load data via lib dotenv"""
        if self.has_dotenv and self.dotenv is not None:
            self.dotenv.load_dotenv()

    def print_rich(self, obj: Any) -> bool:
        """print data to console via lib rich"""
        if self.has_rich and self.rich is not None:
            from rich.console import Console
            from rich.pretty import Pretty
            console = Console()
            console.print(Pretty(obj, indent_guides=True, indent_size=2))
            return True
        return False

    def toml_dumps(self, data: dict) -> Optional[str]:
        """print data in toml format"""
        if self.has_tomliw and self.tomli_w is not None:
            return self.tomli_w.dumps(data)
        return None

_libs = _LibWrapper()

class ExportFormat(Enum):
    """Formats available for exporting the configuration."""
    JSON = 0
    TOML = 1

ConfigModelT = TypeVar('ConfigModelT', bound='ConfigModel')

class ConfigAttrMetadata(BaseModel):
    """Holds metadata about a config field for help-text and documentation generation."""
    model: str
    name: str
    fullname: str
    type: str
    raw_type: Any
    description: str = ''
    default: Any = None

class ConfigModel(BaseModel):
    """
    The core configuration class. Inherit from this to define your config schema.
    Provides logic for loading, merging, and validating configuration data.
    """

    @classmethod
    def _get_attr_metadata(cls, model: Type[BaseModel], _path: str = "") -> list[ConfigAttrMetadata]:
        field_separator = "__"
        f = []
        for name, info in sorted(model.model_fields.items()):
            f_fullname = f"{_path}{field_separator}{name}" if _path else name
            raw_annotation = info.annotation

            origin = getattr(raw_annotation, "__origin__", None)
            args = get_args(raw_annotation)

            target_type = raw_annotation
            if origin is Union:
                filtered_args = [a for a in args if a is not None and not isinstance(None, a)]
                if filtered_args:
                    target_type = filtered_args[0]

            if target_type is not None and hasattr(target_type, "__name__"):
                type_name = target_type.__name__
            elif origin is list:
                inner_args = get_args(target_type)
                inner_name = inner_args[0].__name__ if inner_args and hasattr(inner_args[0], "__name__") else "Any"
                type_name = f"list[{inner_name}]"
            else:
                type_name = str(target_type).replace("<class '", "").replace("'>", "")

            description = f"{info.description or ''} {type_name}".strip()

            f.append(ConfigAttrMetadata(
                model=model.__name__,
                name=name,
                fullname=f_fullname,
                raw_type=raw_annotation,
                type=type_name,
                description=description,
                default=info.default if info.default is not None else None
            ))

            if isinstance(target_type, type) and issubclass(target_type, BaseModel):
                f += cls._get_attr_metadata(target_type, f_fullname)
            elif origin is list and args:
                list_item_type = args[0]
                if isinstance(list_item_type, type) and issubclass(list_item_type, BaseModel):
                    f += cls._get_attr_metadata(list_item_type, f_fullname)
        return f

    @classmethod
    def _add_flat_key_value_to_nested_dict(cls, target_dict: dict, full_name: str, value: Any, field_separator: str):
        parts = full_name.split(field_separator)
        current_level = target_dict
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current_level[part] = value
            else:
                if part not in current_level or not isinstance(current_level[part], dict):
                    current_level[part] = {}
                current_level = current_level[part]

    @classmethod
    def _deep_merge(cls, dict1: dict, dict2: dict) -> dict:
        for key, value in dict2.items():
            if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
                dict1[key] = cls._deep_merge(dict1[key], value)
            else:
                dict1[key] = value
        return dict1

    @classmethod
    def _set_frozen2(cls, model: Type[BaseModel]) -> None:
        model.model_config["frozen"] = True
        for info in model.model_fields.values():
            annotation = info.annotation
            origin = getattr(annotation, "__origin__", None)
            args = get_args(annotation)
            target = annotation
            if origin is Union:
                filtered = [a for a in args if a is not None and not isinstance(None, a)]
                if filtered:
                    target = filtered[0]

            if isinstance(target, type) and issubclass(target, BaseModel):
                cls._set_frozen2(target)
            elif origin is list and args:
                list_item_type = args[0]
                if isinstance(list_item_type, type) and issubclass(list_item_type, BaseModel):
                    cls._set_frozen2(list_item_type)
        model.model_rebuild(force=True)
        logging.debug("🔧 [TypeSaveConfig] Applied frozen state to: %s", model.__name__)

    @classmethod
    def _load_toml(cls, filenames: list[str]) -> dict:
        toml_config = {}
        for toml_file in filenames:
            path = Path(toml_file)
            if not path.exists():
                logging.warning("⚠️ [TypeSaveConfig] TOML file not found: %s", path)
                continue
            try:
                with open(path, "rb") as f:
                    new_data = tomllib.load(f)
                    toml_config = cls._deep_merge(toml_config, new_data)
                    logging.debug("🔧 [TypeSaveConfig] Merged TOML: %s", path)
            except tomllib.TOMLDecodeError as e:
                logging.warning("❌ [TypeSaveConfig] Failed to parse TOML %s: %s", path, e)
        return toml_config

    @classmethod
    def _load_json(cls, filenames: list[str]) -> dict:
        json_config = {}
        for json_file in filenames:
            path = Path(json_file)
            if not path.exists():
                logging.warning("⚠️ [TypeSaveConfig] JSON file not found: %s", path)
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    new_data = json.load(f)
                    json_config = cls._deep_merge(json_config, new_data)
                    logging.debug("🔧 [TypeSaveConfig] Merged JSON: %s", path)
            except json.JSONDecodeError as e:
                logging.warning("❌ [TypeSaveConfig] Failed to parse JSON %s: %s", path, e)
        return json_config

    @classmethod
    def _load_cli_json_style(cls, prefix: str, sep: str) -> dict:
        cli_config = {}
        prefix_lower = prefix.lower()
        metadata_map = {m.fullname: m for m in cls.get_metadata()}
        found_keys = []

        for arg in sys.argv[1:]:
            if arg.startswith("--") and "=" in arg:
                key_part, val_str = arg.split("=", 1)
                clean_key = key_part.lstrip("-")
                if clean_key.startswith(prefix_lower):
                    config_path = clean_key[len(prefix_lower):].lstrip("_")
                    if config_path in metadata_map:
                        try:
                            parsed_val = json.loads(val_str)
                        except (json.JSONDecodeError, TypeError):
                            parsed_val = val_str
                        cls._add_flat_key_value_to_nested_dict(cli_config, config_path, parsed_val, sep)
                        found_keys.append(clean_key)

        if found_keys:
            logging.debug("🔧 [TypeSaveConfig] CLI keys loaded: %s", ", ".join(found_keys))
        else:
            logging.debug("ℹ️ [TypeSaveConfig] No matching CLI found (Prefix: --%s)", prefix_lower)
        return cli_config

    @classmethod
    def _load_env(cls, prefix: str, sep: str) -> dict:
        env_config = {}
        prefix_upper = prefix.upper()
        _libs.load_dotenv()
        found_keys = []

        for m in cls.get_metadata():
            env_name = prefix_upper + m.fullname.upper()
            env_value = os.getenv(env_name)
            if env_value is not None:
                cls._add_flat_key_value_to_nested_dict(env_config, m.fullname, env_value, sep)
                found_keys.append(env_name)

        if found_keys:
            logging.debug("🔧 [TypeSaveConfig] ENV keys loaded: %s", ", ".join(found_keys))
        else:
            logging.debug("ℹ️ [TypeSaveConfig] No matching ENV found (Prefix: %s)", prefix_upper)
        return env_config

    @classmethod
    def _format_errors(cls, e: ValidationError, prefix: str, sep: str) -> str:
        error_messages = []
        for error in e.errors():
            loc_path = sep.join(map(str, error["loc"]))
            env_name = f"{prefix.upper()}{loc_path.upper()}"
            cli_flag = f"--{prefix.lower()}{loc_path.lower()}=value"
            msg = (
                f"\n❌ Field: '{loc_path}'"
                f"\n   Issue: {error['msg']} ({error['type']})"
                f"\n   How to fix: Env: export {env_name}=<value> | CLI: {cli_flag}"
            )
            error_messages.append(msg)
        return "".join(error_messages)

    def print_config(self) -> None:
        """Pretty-prints the current configuration. Uses 'rich' if available."""
        if not _libs.print_rich(self):
            print("-" * 10, self.__class__.__name__, "-" * 10)
            print(self.model_dump_json(indent=2))

    def export(self, frmt: ExportFormat) -> str:
        """Exports the configuration as a TOML or JSON string."""
        if frmt == ExportFormat.TOML:
            res = _libs.toml_dumps(self.model_dump())
            if res:
                return res
            logging.warning("🔧 [TypeSaveConfig] tomli-w not installed, fallback to JSON.")
        return self.model_dump_json(indent=2)

    @classmethod
    def print_help(cls) -> None:
        """Prints help documentation for all available config fields."""
        for a in cls.get_metadata():
            print(f"{a.name} / {a.fullname}")
            print(f"{a.description}")
            print(f"type={a.type} | default={a.default}")

    @classmethod
    def get_metadata(cls) -> list[ConfigAttrMetadata]:
        """Returns a list of metadata for every field in the config model."""
        return cls._get_attr_metadata(cls)

    @classmethod
    def load(cls: Type[ConfigModelT], toml_files: Optional[list[str]] = None,
             json_files: Optional[list[str]] = None, load_env: bool = True,
             load_cli: bool = True, data: Optional[dict[Any, Any]] = None,
             readonly: bool = True, prefix: str = "TSC_") -> Optional[ConfigModelT]:
        """
        Loads the configuration from various sources.

        Args:
            toml_files: List of TOML file paths to load.
            json_files: List of JSON file paths to load.
            load_env: Whether to load from Environment Variables.
            load_cli: Whether to load from CLI arguments.
            data: Initial dictionary of values (lowest priority).
            readonly: If True, the resulting config object is immutable.
            prefix: Prefix for CLI flags and Environment variables.
        """
        field_separator = "__"
        merged: dict[Any, Any] = data if data is not None else {}

        toml_list = toml_files if toml_files is not None else []
        json_list = json_files if json_files is not None else []

        merged = cls._deep_merge(merged, cls._load_toml(toml_list))
        merged = cls._deep_merge(merged, cls._load_json(json_list))

        if load_cli:
            merged = cls._deep_merge(merged, cls._load_cli_json_style(prefix, field_separator))
        if load_env:
            merged = cls._deep_merge(merged, cls._load_env(prefix, field_separator))

        try:
            instance = cls(**merged)
            if readonly:
                cls._set_frozen2(cls)
            logging.info("🔧 [TypeSaveConfig] '%s' loaded (readonly=%s)", cls.__name__, readonly)
            return instance
        except ValidationError as e:
            err_msg = cls._format_errors(e, prefix, field_separator)
            logging.error("🔧 [TypeSaveConfig] Validation failed: %s", err_msg)
            return None

    @classmethod
    def _set_frozen(cls, model: Type[BaseModel]) -> None:
        cls._set_frozen2(model)

    @classmethod
    def _load_cli(cls, prefix: str, sep: str) -> dict:
        return cls._load_cli_json_style(prefix, sep)
