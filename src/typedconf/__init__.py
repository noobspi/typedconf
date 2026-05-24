"""
## TypedConf

A lightweight, type-safe configuration management library powered by Pydantic.
It centralizes application settings by merging data from multiple sources with a
defined priority (Environment > CLI > JSON > TOML > Defaults).

- **Type-Safe:** Built on Pydantic, ensuring configuration values are validated at runtime.
- **IDE Support:** Full type-hinting, thanks to pydantic, for seamless development.
- **Nested Support:** Easily handle complex configuration structures.
- **TOML and JSON Interface:** Load configuration from toml and/or json files.
- **CLI and Environment Interface:** Load configuration data from CLI interface (--cfg_myint=1) and/or ENV varables (export CFG_MYINT=1).
- **Layered Configuration:** Merges configuration data with a clear priority: ENV > CLI > JSON > TOML > Payload > Defaults
- **Immutability**: Configuration data is readonly (default) after loading.
- **Self-Documenting:** Generate help text from your configuration/pydantic schema.

### Usage Example:
```
    class MyConfig(ConfigModel):
        db_url: str = "localhost"
        debug: bool = False

    cfg = MyConfig.load(toml_files=["config.toml"])

    # Access values
    print(cfg.db_url)
```
### CLI and ENV Syntax:
- ENV: `export CFG_DB_URL="postgres://..."`
- CLI: `python script.py --cfg_db_url="postgres://..."`
- Lists and dicts (CLI only): `--cfg_mylist='["a", "b"]'` (Uses JSON-style parsing)
"""
from .core import ConfigModel, ConfigAttrMetadata, ConfigError, UserNeedsHelp

__all__ = [
    "ConfigModel",
    "ConfigError",
    "ConfigAttrMetadata",
    "UserNeedsHelp"
]

__version__ = "0.1.0"
