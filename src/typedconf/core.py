"""
TypedConf. A lightweight, type-safe configuration management library powered by Pydantic v2.
It centralizes application settings by merging data from multiple sources with a
defined priority (Environment > CLI > JSON > TOML > Defaults).
"""

import json
import logging
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, Type, TypeVar, Union, get_args, Optional
from pydantic import BaseModel, ValidationError, computed_field


_DEFAULT_CLI_LONGOPTIONS = '--'
_DEFAULT_CLI_ENV_PREFIX = 'cfg_'
_DEFAULT_CLI_ENV_SEPARATOR = '__'

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class _LibWrapper:
    """
    Internal abstraction for optional third-party libraries.
    Ensures the library remains functional even 'tomli-w' is not installed.
    """
    def __init__(self):
        self.tomli_w, self.has_tomliw = self._import("tomli_w")
        logging.debug("[TypedConf] Found optional python-package 'tomli-w': TOML-Export enabled.")

    @staticmethod
    def _import(name: str):
        try:
            return __import__(name), True
        except ImportError:
            return None, False

    def toml_dumps(self, data: dict) -> Optional[str]:
        """dumps data in toml format"""
        if self.has_tomliw and self.tomli_w is not None:
            return self.tomli_w.dumps(data)
        return None
_libs = _LibWrapper()



class ConfigError(Exception):
    """
    Raised when configuration validation fails. Either data for the field(s) is missing, 
    or data (from toml|json|cli|env|source) is invalid. fields[] is a list of fieldnames 
    containing a pydantic validation-error. 
    TODO: currently get from pydantic only(!) the very 1st validation-error while loading data.
    Therefore fields has alwyas only 1 item.
    """
    def __init__(self, message: str, fields: list[str]):
        self.fields = fields
        super().__init__(message)

class UserNeedsHelp(Exception):
    """
    Raised, when the (a) shell-user (caller aof the script/application) added `--help` to the cli AND (b) `cli_enable_help=True` on load(9)
    str(e) = get_cli_helptext, including the correct `cli-prefix`
    """
    def __init__(self, helptext: str):
        super().__init__(helptext)


class ConfigAttrMetadata(BaseModel):
    """Holds metadata about a config field for help-text and documentation generation.
    TODO: computed fields don't and can't respect the prefix in classmethod load()?!"""
    model: str
    name: str
    fullname: str
    type: str
    raw_type: Any
    isa_ConfigModel: bool = False
    description: str = ''
    default: Any = None

    @computed_field
    @property
    def default_cli_key(self) -> str:
        """computed field: default cli key for --key=val)"""
        k = f"{_DEFAULT_CLI_LONGOPTIONS}{_DEFAULT_CLI_ENV_PREFIX}{self.fullname}"
        return k.lower()

    @computed_field
    @property
    def default_env_key(self) -> str:
        """computed field: default env key for KEY=VAL"""
        k = f"{_DEFAULT_CLI_ENV_PREFIX}{self.fullname}"
        return k.upper()


ConfigModelT = TypeVar('ConfigModelT', bound='ConfigModel')
class ConfigModel(BaseModel):
    """
    TypedConf's core class. Inherit to define your own config-schema.
    TypedConf is a lightweight, type-safe configuration management library powered by
    Pydantic. It provides logic for loading configurations from TOML-, JSON-files, CLI, ENV.
    Plus validating the configuration by pydantic :)
    """

    model_config = {
        "frozen": True,              # configuration is readonly
        "extra": "forbid",           # raise error, when loading unknown extra data
        "validate_default": True,    # validate default values foreach field
        "validate_assignment": True, # validate when assigning a new value
    }


    @classmethod
    def _get_attr_metadata(cls, model: Type[BaseModel], _path: str = "") -> list[ConfigAttrMetadata]:
        """Returns flat list of all attributes (ConfigAttrMetadata)"""
        field_separator = _DEFAULT_CLI_ENV_SEPARATOR
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

            description = f"{info.description or ''}"
            isa_pydantic_model = isinstance(target_type, type) and issubclass(target_type, BaseModel)

            f.append(ConfigAttrMetadata(
                model = model.__name__,
                name = name,
                fullname = f_fullname,
                raw_type = raw_annotation,
                isa_ConfigModel = isa_pydantic_model,
                type = type_name,
                description = description,
                default = info.default if info.default is not None else None
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
        """ouflattens a key to a nested dict"""
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
        """merges deeply 2 dicts"""
        for key, value in dict2.items():
            if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
                dict1[key] = cls._deep_merge(dict1[key], value)
            else:
                dict1[key] = value
        return dict1


    @classmethod
    def _set_frozen(cls, model: Type[BaseModel]) -> None:
        """sets configuration recursiv to readonly"""
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
                cls._set_frozen(target)
            elif origin is list and args:
                list_item_type = args[0]
                if isinstance(list_item_type, type) and issubclass(list_item_type, BaseModel):
                    cls._set_frozen(list_item_type)
        model.model_rebuild(force=True)
        logging.debug("[TypedConf] Applied frozen-state/readonly to '%s'", model.__name__)


    @classmethod
    def _load_toml(cls, filenames: list[str]) -> dict:
        """loads data from a toml file-list"""
        toml_config = {}
        for toml_file in filenames:
            path = Path(toml_file)
            if not path.exists():
                logging.warning("[TypedConf] TOML file not found: %s", path)
                continue
            try:
                with open(path, "rb") as f:
                    new_data = tomllib.load(f)
                    toml_config = cls._deep_merge(toml_config, new_data)
                    logging.debug("[TypedConf] TOML read from: %s", path)
            except tomllib.TOMLDecodeError as e:
                logging.warning("[TypedConf] Failed to read & parse TOML %s: %s", path, e)
        return toml_config


    @classmethod
    def _load_json(cls, filenames: list[str]) -> dict:
        """loads data from a json file"""
        json_config = {}
        for json_file in filenames:
            path = Path(json_file)
            if not path.exists():
                logging.warning("[TypedConf] JSON file not found %s", path)
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    new_data = json.load(f)
                    json_config = cls._deep_merge(json_config, new_data)
                    logging.debug("[TypedConf] JSON read from %s", path)
            except json.JSONDecodeError as e:
                logging.warning("[TypedConf] Failed to read & parse JSON %s: %s", path, e)
        return json_config


    @classmethod
    def _load_cli(cls, prefix: str, sep: str) -> dict:
        """loads data from CLI. lists are available via json-style"""
        cli_config = {}
        prefix_lower = prefix.lower()
        metadata_map = {m.fullname: m for m in cls.get_metadata()}
        found_keys = []

        for arg in sys.argv[1:]:
            if arg.startswith(_DEFAULT_CLI_LONGOPTIONS) and "=" in arg:
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
                        found_keys.append(f"{_DEFAULT_CLI_LONGOPTIONS}{clean_key}")

        if found_keys:
            logging.debug("[TypedConf] CLI read from [%s]", ",".join(found_keys))
        else:
            logging.debug("[TypedConf] CLI nothing found (Prefix: %s%s)", _DEFAULT_CLI_LONGOPTIONS, prefix_lower)
        return cli_config

    @classmethod
    def _load_env(cls, prefix: str, sep: str) -> dict:
        """loads data from ENV"""
        env_config = {}
        prefix_upper = prefix.upper()
        found_keys = []

        for m in cls.get_metadata():
            env_name = prefix_upper + m.fullname.upper()
            env_value = os.getenv(env_name)
            if env_value is not None:
                cls._add_flat_key_value_to_nested_dict(env_config, m.fullname, env_value, sep)
                found_keys.append(env_name)

        if found_keys:
            logging.debug("[TypedConf] ENV read from [%s]", ",".join(found_keys))
        else:
            logging.debug("[TypedConf] ENV nothing found (Prefix: %s)", prefix_upper)
        return env_config


    @classmethod
    def _format_validationerror2(cls, e: ValidationError) -> str:
        """Format pydantics ValidationError (for logging)"""
        t = str(e).replace('\n', ' ')
        err_str = re.sub(r'\s+', ' ', t)
        return err_str

    @classmethod
    def _format_validationerror(cls, e: ValidationError) -> str:
        """Format pydantics ValidationError (for logging)"""
        error_messages = []
        #error_messages.append("Key missing or value invalid!")
        metadata_map = {(m.model, m.name): m for m in cls.get_metadata()}

        for error in e.errors():
            field_name = str(error["loc"][-1]) #'.'.join(map(str, error["loc"]))
            model_name = str(e.title)
            m = metadata_map.get((model_name, field_name))
            #print(m, "\n", model_name, field_name)
            if m:
                model_classname = f"{m.model}.{m.name}"
                cli_fullname = f"{_DEFAULT_CLI_LONGOPTIONS}{_DEFAULT_CLI_ENV_PREFIX}{m.fullname}"
                error_messages.append(f"{model_classname} ({cli_fullname}): {error['msg']}; {error['type']}.")

        #validation_input_data = e.errors()[0]['input']
        return ' '.join(error_messages)


    ###################### Public API ###########################

    @classmethod
    def user_needs_help(cls) -> bool:
        """Returns True, when a typical help cli param (--help, -h) is used by the user"""
        cli_help_keys = {'--help', '-h', '-?'}
        for arg in sys.argv[1:]:
            if arg in cli_help_keys:
                return True
        return False


    @classmethod
    def get_cli_helptext(cls, prefix:str|None = None) -> str:
        """Returns help-text documentation for all available config fields. Respects cli-prefix (or uses the default)"""
        prefix = _DEFAULT_CLI_ENV_PREFIX if not prefix else prefix
        hlines = []
        for a in cls.get_metadata():
            cli_argument = f"{_DEFAULT_CLI_LONGOPTIONS}{prefix}{a.fullname}"
            model_fieldname = f"{a.model}.{a.name}"
            if not a.isa_ConfigModel:   # exclude pydantic/ConfigModels from cli-list
                hl  = f"{cli_argument} ({model_fieldname})\n"
                hl += f"  type={a.type}, default={a.default}"
                if a.description:
                    hl += (f"\n  {a.description}")
                hlines.append(hl)

        return "\n\n".join(hlines)


    def dumps_toml(self) -> str|None:
        """Dumps the configuration as TOML string. Uses optional python-package "tomli-w" to work. 
           Returns None, if package tomli-w is not installed."""
        if _libs.has_tomliw:
            return _libs.toml_dumps(self.model_dump())
        else:
            return None

    def dumps_json(self, pretty:bool=True) -> str:
        """Dumps the configuration as JSON string."""
        return self.model_dump_json(indent=2) if pretty else self.model_dump_json()



    @classmethod
    def get_metadata(cls) -> list[ConfigAttrMetadata]:
        """Returns a list of metadata (ConfigAttrMetadata) for every field in the config model."""
        return cls._get_attr_metadata(cls)


    @classmethod
    def load(cls: Type[ConfigModelT],
             toml_files: Optional[list[str]] = None,
             json_files: Optional[list[str]] = None,
             load_env: bool = True,
             load_cli: bool = True,
             payload: Optional[dict[Any, Any]] = None,
             cli_prefix: Optional[str | None] = None,
             cli_separator: Optional[str | None] = None,
             cli_help_enabled: bool = False,
             #readonly: bool = True, #TODO: Re-Think a writeable configuration for the user...
             ) -> ConfigModelT:
        """
        Loads the configuration from various sources.
        Merge data in this order: ENV > CLI > JSON > TOML > Payload > Defaults (ENV has highest priority).

        Raises:
            `ConfigError`, if configuration validation fails.
            `UserNeedsHelp`, if cli_help_enabled==True and adds `--help` to the cli/shell
        
        Args:
            toml_files: List of TOML file paths to load (field from last file in list wins).
            json_files: List of JSON file paths to load (field from last file in list wins).
            load_env: Whether to load from Environment Variables. Default = True
            load_cli: Whether to load from CLI arguments. Default = True
            payload: Initial dictionary of values (lowest priority).
            cli_prefix: change the default prefix for CLI and ENV interface. Default = 'cfg_'
            cli_separator: change the default fullname-separator. Default = '__' => NOT YET IMPLEMENTED
            cli_help_enabled: if set, --help arguments will be added to the cli-interface. Raises UserNeedsHelp if, --help; exception message = cli_helptext(prefix)
            readonly: If True, the resulting config object is immutable. Default = True
        """
        prefix = _DEFAULT_CLI_ENV_PREFIX if not cli_prefix else cli_prefix
        separator = _DEFAULT_CLI_ENV_SEPARATOR if not cli_separator else _DEFAULT_CLI_ENV_SEPARATOR #TODO

        if cli_help_enabled:
            if cls.user_needs_help():
                raise UserNeedsHelp(cls.get_cli_helptext(prefix))

        # load data from spource-code payload
        merged: dict[Any, Any] = payload if payload is not None else {}

        # load from toml
        toml_list = toml_files if toml_files is not None else []
        merged = cls._deep_merge(merged, cls._load_toml(toml_list))

        # load from json
        json_list = json_files if json_files is not None else []
        merged = cls._deep_merge(merged, cls._load_json(json_list))

        # load from cli- and env-interface
        if load_cli:
            merged = cls._deep_merge(merged, cls._load_cli(prefix, separator))
        if load_env:
            merged = cls._deep_merge(merged, cls._load_env(prefix, separator))

        # init/load/validate pydantic BaseModel with merged data
        try:
            instance = cls.model_validate(merged)
            # if not readonly:
            #     class RWConfigModel(cls):
            #         """A writeable ConfigModel"""
            #         model_config={'frozen':False}
            #     RWConfigModel.__name__ = f"Rw{cls.__name__}"
            #     RWConfigModel.__qualname__ = f"Rw{cls.__qualname__}"
            #     instance = RWConfigModel.model_validate(merged)

            logging.info("[TypedConf] Configuration '%s' loaded (readonly)", cls.__name__)
            return instance # type: ignore
        except ValidationError as e:
            err = e.errors()[0]
            err_msg = cls._format_validationerror2(e)
            err_field = str(err["loc"][-1]) #'.'.join(map(str, error["loc"]))
            _model_name = str(e.title)

            logging.warning("[TypedConf] Loading field '%s' failed! %s", err_field, err_msg)
            raise ConfigError(err_msg, [err_field,]) from e
