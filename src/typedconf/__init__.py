"""
## TypedConf

A lightweight, type-safe configuration management library powered by Pydantic v2.
It centralizes application settings by merging data from multiple sources with a
defined priority (Environment > CLI > JSON > TOML > Defaults).

Key Features:
- Automatic Merging: Priority-based merging of various config sources.
- Deep Nesting: Supports nested Pydantic models using `__` as a separator.
- Type Safety: Full validation of types, including lists and Enums.
- Optional Dependencies: Enhanced output via `rich`, `.env` support via `python-dotenv`,
  and TOML exporting via `tomli-w`.
- Immutability: Config can be optionally 'frozen' (readonly) after loading.

### Usage Example:
```
    class MyConfig(ConfigModel):
        db_url: str = "localhost"
        debug: bool = False

    # Load from all sources with default prefix 'TSC_'
    cfg = MyConfig.load(toml_files=["config.toml"])

    # Access values
    print(cfg.db_url)
```
### CLI & Env Syntax:
- ENV: `export CFG_DB_URL="postgres://..."`
- CLI: `python script.py --cgf_db_url="postgres://..."`
- Lists (CLI): `--cgf_tags='["a", "b"]'` (Uses JSON-style parsing)
"""
from .core import ConfigModel, ConfigError, ConfigAttrMetadata

__all__ = [
    "ConfigModel",
    "ConfigError",
    "ConfigAttrMetadata",
]

__version__ = "0.1.0"
