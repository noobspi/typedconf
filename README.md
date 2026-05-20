# TypedConf

A lightweight, type-safe configuration management library powered by Pydantic.
Following the [12-factor application guide](https://12factor.net/config), it centralizes your application configuration/settings 
by merging data from multiple sources with a defined priority (Environment > CLI > JSON > TOML > Defaults).
Heavily inspired by
[dynaconf](https://www.dynaconf.com/),
[pydantic](https://pydantic.dev/docs/validation/latest/get-started/) and
[fastapi](https://fastapi.tiangolo.com/).

## Key Features

- **Type-Safe:** Built on Pydantic, ensuring configuration values are validated at runtime.
- **IDE Support:** Full type-hinting, thanks to pydantic, for seamless development.
- **Nested Support:** Easily handle complex configuration structures.
- **TOML and JSON Interface:** Load configuration from toml and/or json files.
- **CLI and ENVironment Interface:** Load configuration data from CLI interface (--cfg_myint=1) and/or ENV varables (export CFG_MYINT=1).
- **Layered Configuration:** Merges configuration data with a clear priority: ENV > CLI > JSON > TOML > Payload > Defaults
- **Immutability**: Configuration data is readonly (default) after loading.
- **Self-Documenting:** Generate help text from your configuration/pydantic schema.

---

## Basic Usage

Define your configuration schema by inheriting from `ConfigModel`. Use standard Pydantic `Field` definitions to add descriptions, constraints, or default values.

```python
from pydantic import Field
from typedconf import ConfigModel, ConfigError

class DatabaseConfig(ConfigModel):
    url: str = "sqlite:///default.db"
    port: int = 5432

class AppConfig(ConfigModel):
    app_name: str = "no-name"
    debug: bool = False
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)

# Load configuration (immutable/readonly by default)
try:
    conf = AppConfig.load(toml_files=['config.toml'])
    print(f"Starting {conf.app_name}...")
except ConfigError as e:
    # Print helpful CLI documentation if configuration fails
    print(AppConfig.cli_helptext())
```

To provide a complete picture, here is how your configuration files should be structured to work seamlessly with the nested models in your examples.

### Example Configuration Files

When using `ConfigModel`, the structure of your files must mirror the hierarchy of your classes.
TOML is perfect for nested configurations using tables.

```toml
app_name = "My Application"
debug = true

[db]
url = "postgresql://localhost:5432/mydb"
port = 5432
```

JSON requires nested objects to reflect the same structure:

```json
{
  "app_name": "My Application",
  "debug": true,
  "db": {
    "url": "postgresql://localhost:5432/mydb",
    "port": 5432
  }
}
```

## Configuration File Formats

Your TOML and JSON files should mirror the structure of your `ConfigModel` classes.

- **TOML:** Use tables (e.g., `[database]`) to define nested sub-models.
- **JSON:** Use nested objects to define sub-models.

If you have a `DatabaseConfig` inside an `AppConfig`, your file structure must look like this:

```toml
# config.toml
app_name = "MyApp"

[db]
url = "db://server:1234/db"
port = 5432
```

This mapping allows **TypedConf** to automatically map file keys to your Pydantic model fields, ensuring type safety and easy configuration management.

## Priority Chain

TypedConf merges sources in a specific order. Higher-priority sources overwrite lower-priority ones.

1. **Environment Variables (Highest):** Overrides all other sources (e.g., `CFG_DB__PORT`).
2. **CLI Arguments:** Passed via command-line (e.g., `--cfg_db__port=9000`).
3. **JSON Files:** Merged from the provided list in the order specified.
4. **TOML Files:** Merged from the provided list in the order specified.
5. **Payload (Dict):** A dictionary passed directly to the `.load()` method.
6. **Defaults (Lowest):** Values defined directly in your `ConfigModel` class.

*Note: The system performs a **deep merge**, preserving nested structures when partial overrides are provided.*

## Environment Variables and CLI Interface

TypedConf allows runtime overrides without modifying configuration files.

**CLI Usage**
Arguments use the prefix `cfg_` followed by the field path. Use `__` to traverse nested models.

```bash
# basic cli interface --cfg_key=value
python main.py --cfg_db__loglevel=4 --cfg_app_name='my-cli-app'
python main.py --cgf_db_url="postgres://..."

# lists in cli uses JSON-style parsing
python main.py --cgf_tags='["t1", "t2"]'
```

**Environment Variable Usage**
Environment variables follow the same naming convention but are strictly **UPPERCASE**. They hold the highest priority. Json-styled lists aren't possible in the ENV interface :smiley:

```bash
export CFG_DB_URL="postgres://..."
uv run main.py

# env- overwrites cli-interface
CFG_APP_NAME='my-env-app' uv run main.py --cfg_app_name='my-cli-app'  # => my-env-app
```

## Advanced Features

### Exporting Configurations

Export your current configuration instance to JSON or TOML format for debugging or deployment:

```python
from typedconf import ExportFormat

# Export to TOML string
print(conf.export_config(ExportFormat.TOML))
```

*Hint: Exporting in TOML Format requires the package "tomli_w". install it with `pip install tomli_w`*

### Automatic Help Generation

Automatically generate documentation for your users by calling `print_help()`. This extracts field types, defaults, and descriptions directly from your model definition.

```python
AppConfig.print_help(header="My Application Settings:", footer="See docs for more info.")
```
